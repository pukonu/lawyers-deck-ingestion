# UK Acts Indexing Guide

This document specifies how captured Act JSON files under `data/acts/` (see `ACTS_README.md`) are imported into the application database and indexed for keyword search, semantic search, and RAG. It mirrors the existing judgment pipeline:

```
data/acts/{type}/{year}/{number}.json
        │
        ▼  app/src/lib/db/import-acts.ts          (to be written)
PostgreSQL: acts, act_sections
        │
        ▼  app/src/lib/db/embed-acts.ts           (to be written)
PostgreSQL: act_chunks (vector 1536) + HNSW + tsvector
        │
        ├─► retrieval / keyword search             (extend existing search libs)
        └─► optional Qdrant export                 (extend push script)
```

Status: **specification only — no scripts, schema, or migrations have been created yet.**

## 1. Database Schema (Drizzle, add to `app/src/lib/db/schema.ts`)

### `acts`

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `legislation_uri` | text, unique, not null | e.g. `ukpga/2021/1` — import key, mirrors `judgments.tna_uri` |
| `legislation_type` | text, not null | `ukpga`, `asp`, `asc`, `anaw`, `nia`, ... |
| `year` | int | calendar year (regnal-year Acts: derive or null) |
| `number` | int | |
| `title` | text, not null | short title, e.g. "Pension Schemes Act 2021" |
| `long_title` | text | |
| `version_captured` | text | `current` / `enacted` / date |
| `enactment_date` | date | |
| `extent` | text[] | subset of E, W, S, NI |
| `status` | text | `in_force`, `partially_in_force`, `prospective`, `repealed`, `unknown` |
| `has_unapplied_effects` | boolean | warn users the text may lag |
| `format` | text | `xml` / `pdf_only` |
| `contents` | jsonb | table of contents |
| `full_text` | text | |
| `html_url`, `xml_url`, `pdf_url` | text | |
| `fetched_at` | timestamptz | |
| enrichment columns | | `short_description`, `area_of_law` text[], `key_provisions` jsonb, `related_acts` jsonb, `index_terms` text[], `catchwords` text[], `confidence` jsonb — nullable until enrichment runs |
| `is_enriched` | boolean generated/maintained | same semantics as judgments |
| `search_vector` | tsvector generated | see §3 |

### `act_sections`

One row per section and schedule — this is the citation unit and the chunk source.

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `act_id` | uuid fk → acts | cascade delete |
| `section_id` | text | `section-1`, `schedule-2` (stable within the Act) |
| `kind` | text | `section` / `schedule` |
| `number` | text | "1", "2A" — text because of inserted sections (2A, 2B) |
| `heading` | text | |
| `part` | text | containing Part/Chapter label |
| `repealed` | boolean | |
| `text` | text | plain text of the provision |
| `position` | int | document order |

Unique index on (`act_id`, `section_id`).

### `act_chunks`

Same shape as `judgment_chunks`:

| Column | Type | Notes |
|---|---|---|
| `id` | uuid pk | |
| `act_id` | uuid fk → acts | |
| `section_id` | text nullable | which provision the chunk came from |
| `chunk_index` | int | |
| `content` | text | |
| `metadata` | jsonb | `{ kind: 'synopsis' | 'section' | 'schedule', sectionNumber?, heading? }` |
| `embedding` | vector(1536) | `text-embedding-3-small`, HNSW index like judgments |

### `judgment_statutes` linkage

Add nullable `act_id` (fk → acts) to `judgment_statutes`. A post-import linking pass matches `judgment_statutes.title` to `acts.title`:

1. Normalise both sides: trim, collapse whitespace, unify quotes, strip trailing year iff the title also contains it, lowercase.
2. Exact normalised title match first; fall back to title-without-year + year extracted from the statute string.
3. Never fuzzy-match below exact/near-exact — a wrong statute link is worse than none. Leave `act_id` null when ambiguous.

## 2. Import Script (`import-acts.ts`)

Model on `import-judgments.ts`:

- Default input dir `ingestion/data/acts`, override with `--dir`.
- Walk `{type}/{year}/{number}.json` (skip `index/`), require `legislation_uri`, skip files missing it.
- Resumable: skip URIs already in `acts` unless `--refresh` or `--uri ukpga/2021/1`.
- Upsert `acts` row, delete + reinsert `act_sections` for that Act (sections change wholesale when a revised version is re-fetched).
- `pdf_only` records import metadata rows with empty text — they should appear in browse/citation lookup but not in semantic search.
- After import, run the judgment_statutes linking pass (can be a `--link` flag or separate script).
- Makefile targets to add: `db-import-acts`, `db-import-acts-sample`.

## 3. Keyword Search (tsvector)

Add a generated `search_vector` on `acts` in `migrate.ts`, weighted consistently with judgments:

- **A**: `title`, `short_description`
- **B**: `long_title`, `area_of_law`, `index_terms`
- **C**: `catchwords`, section headings (materialise a concatenated `section_headings` text column or fold headings into the vector at import time)
- **D**: `full_text`

Extend `app/src/lib/search/keyword.ts` to query both corpora and return a discriminated result type (`kind: 'judgment' | 'act'`). Acts should also be findable by citation-style queries ("Pension Schemes Act 2021 s 1"): parse trailing `s/section N` and, when the title matches a single Act, boost or deep-link to that section.

## 4. Chunking and Embedding (`embed-acts.ts`)

Reuse the embedding stack (`ai/embeddings.ts`: OpenAI `text-embedding-3-small`, 1536-dim, Gemini fallback), but chunk **structurally, not by character window**:

1. **Synopsis chunk** (1 per Act): title + long title + status/extent line + `short_description` (when enriched) + list of Part headings. Metadata `{ kind: 'synopsis' }`.
2. **Section chunks**: one chunk per section, prefixed with context so the embedding is self-contained: `"{Act title}, {Part heading}, Section {number}: {heading}\n{text}"`. Sections longer than ~1,400 chars split on subsection boundaries into multiple chunks sharing `section_id`. Metadata `{ kind: 'section', sectionNumber, heading }`.
3. **Schedule chunks**: same as sections with `kind: 'schedule'`. Long schedules split on paragraph boundaries.
4. Skip `repealed: true` provisions and `pdf_only` Acts.

Chunk size target ~1,100–1,400 chars, matching `ai/chunking.ts` for judgments so cross-corpus similarity scores are comparable.

Run order after import: `db:embed:acts` (new script), idempotent — only embed Acts with no chunks unless `--refresh`.

## 5. Retrieval / RAG Integration

Extend `app/src/lib/ai/retrieval.ts`:

- Hybrid search runs over `judgment_chunks` and `act_chunks`, merged by cosine score. Tag every retrieved chunk with its corpus so the answer can cite "Section 1, Pension Schemes Act 2021" vs a case citation.
- Filters: `legislation_type`, `status` (default exclude `repealed` from RAG context), `extent`, year range.
- When a judgment chunk and an act chunk both surface and `judgment_statutes.act_id` links them, surface that relationship in the context block — "this judgment considered this Act" is high-value grounding.
- Semantic search over acts should not require `is_enriched` (unlike judgments): statutory text is authoritative as-is. Only synopsis quality depends on enrichment.

## 6. Qdrant (optional)

If the Qdrant mirror is in use, extend `push-judgment-chunks.ts` (or add `push-act-chunks.ts`) to push `act_chunks` into the same collection with payload field `corpus: "act"` plus `legislationUri`, `title`, `sectionNumber`, `status`, `extent`. Reads from Postgres, never from the ingestion folder.

## 7. Acceptance Checklist Before Bulk Runs

- [ ] `acts_worker.py` capture reviewed against Fair Use Policy (§1.4 of `ACTS_README.md`); user agent set.
- [ ] 10-Act pilot captured (suggest: Pension Schemes Act 2021, Equality Act 2010, Companies Act 2006, Consumer Rights Act 2015, Data Protection Act 2018, Human Rights Act 1998, Landlord and Tenant Act 1985, Theft Act 1968, Limitation Act 1980, Employment Rights Act 1996) and JSON validated against the schema in `ACTS_README.md` §4.
- [ ] Drizzle schema + migration reviewed; HNSW + tsvector present.
- [ ] Pilot import + embed runs clean; citation query "Equality Act 2010 s 6" returns the disability definition section.
- [ ] judgment_statutes linking pass spot-checked for false positives on the pilot set.
- [ ] Only then run the full `ukpga` backfill, then Phase 2 devolved types.
