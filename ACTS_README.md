# UK Acts Ingestion Guide

This guide defines how to capture UK Acts (primary legislation) from the official UK government source into this ingestion repo, mirroring the judgments workflow (`worker.py` → `data/judgments/`). Companion documents:

- `ACTS_INDEXING_README.md` — how captured acts are imported, chunked, embedded, and indexed in the app database.
- `data/acts/README.md` — local layout of the captured corpus (the `data/` folder is gitignored).

Status: **`acts_worker.py` is implemented and pilot-tested** (Pension Schemes Act 2021, Equality Act 2010, and the PDF-only Metropolis Water Act 1902). No bulk capture has been run yet — do not start it until the plan below is approved.

## 1. Source of Truth

The single authoritative UK government source for Acts is **legislation.gov.uk**, published and managed by The National Archives. It covers all UK primary legislation (Westminster, Scotland, Wales, Northern Ireland), both "as enacted" and "revised" (current, amendments applied) versions.

- Website / API base: `https://www.legislation.gov.uk`
- Developer docs: `https://legislation.github.io/data-documentation/` and `https://www.legislation.gov.uk/developer`
- Licence: **Open Government Licence v3.0** — reuse (including commercial) is permitted with attribution: "Contains public sector information licensed under the Open Government Licence v3.0."
- The National Archives explicitly encourages API use, including crawling and bulk access.

Do not scrape gov.uk guidance pages, parliament.uk bills pages, or third-party mirrors for Act text. Bills (not yet law) are out of scope.

### 1.1 The website *is* the API

Every legislation page is also an API resource:

- Append `/data.xml` to any legislation URI → content as **CLML** (Crown Legislation Markup Language), the canonical structured XML.
- Append `/data.akn` → Akoma Ntoso XML (international legal XML standard).
- Append `/data.htm` → HTML rendering.
- Append `/data.feed` to any list/search page → **Atom feed** (paginated listing).

Examples:

| URL | Returns |
|---|---|
| `https://www.legislation.gov.uk/ukpga/2021/1/data.xml` | Latest revised version of the Pension Schemes Act 2021 as CLML |
| `https://www.legislation.gov.uk/ukpga/2021/1/enacted/data.xml` | The as-enacted version as CLML |
| `https://www.legislation.gov.uk/ukpga/2021/1/contents/data.xml` | Table of contents as XML |
| `https://www.legislation.gov.uk/ukpga/2021/1/resources/data.xml` | Metadata only (title, dates, extent, associated documents) |
| `https://www.legislation.gov.uk/ukpga/2021/1/section/1/data.xml` | A single section as CLML |
| `https://www.legislation.gov.uk/ukpga/data.feed?results-count=100` | Atom feed listing UK Public General Acts, 100 per page |
| `https://www.legislation.gov.uk/ukpga/2020/data.feed` | Atom feed of all UKPGA with year 2020 |
| `https://www.legislation.gov.uk/changes/affected/ukpga/2021/1/data.feed` | Amendments ("effects") affecting an Act |

### 1.2 Legislation types in scope

The URI scheme is `/{type}/{year}/{number}`. Types for Acts (primary legislation):

| Type code | Description | Priority |
|---|---|---|
| `ukpga` | UK Public General Acts (Westminster) — the core statute book | **Phase 1** |
| `asp` | Acts of the Scottish Parliament (1999–) | Phase 2 |
| `asc` | Acts of Senedd Cymru (2020–) | Phase 2 |
| `anaw` | Acts of the National Assembly for Wales (2012–2020) | Phase 2 |
| `nia` | Acts of the Northern Ireland Assembly (2000–) | Phase 2 |
| `ukla` | UK Local Acts | Phase 3 |
| `mwa` | Measures of the National Assembly for Wales (2008–2011) | Phase 3 |
| `mnia` | Measures of the Northern Ireland Assembly | Phase 3 |
| `apgb` | Acts of the Parliament of Great Britain (1707–1800) | Phase 3 (historical) |
| `aep` / `aosp` / `aip` / `apni` | Older English / Scottish / Irish / NI Parliament Acts | Phase 3 (historical) |

Secondary legislation (`uksi`, `ssi`, `wsi`, `nisr`) is **out of scope** for this corpus; it can become `data/instruments/` later if needed.

### 1.3 Versions: enacted vs. revised

For lawyers, the **revised (current) version** is the primary target: it is the law as it stands today with amendments applied. Capture policy:

1. Capture the **latest revised version** as the canonical `full_text` (URI without a version segment, e.g. `/ukpga/2021/1/data.xml`).
2. Record whether unapplied amendments are outstanding (present in CLML metadata `ukm:UnappliedEffects`) so users can be warned the text may lag.
3. Do not capture every historical point-in-time version in Phase 1. Point-in-time URIs (`/ukpga/1985/67/2003-04-01/data.xml`) exist if we ever need them.

Note: revised text is only maintained for most `ukpga` and devolved Acts; many pre-1988 or repealed Acts exist only "as enacted", and a small number of very old Acts are **PDF-only** (no XML). Mark those `"format": "pdf_only"` in the stub and skip full-text capture; do not OCR PDFs in Phase 1.

### 1.4 Fair Use Policy (mandatory)

- Always send a descriptive `User-Agent` (e.g. `lawyersdeck-ingestion/1.0 (contact: <email>)`).
- Hard rate limit: **3,000 requests per 5 minutes per user** (not per IP — do not parallelise across IPs). Exceeding it returns `403`.
- Use a conservative crawl rate: **~1–2 requests/second**, matching the pacing already used by `worker.py` for judgments.
- Follow `https://www.legislation.gov.uk/robots.txt` including any `crawl-delay`.
- Handle response codes: `202` (dynamically generated resource, retry after ≥10s), `300` (ambiguous URI — old Acts sharing year/number; resolve via the returned list), `403` (rate limited — back off), `503`/`504` (wait ≥5 minutes).
- For incremental updates after the initial capture, use the **New Legislation feed** (`/new/data.feed`) and the **Publication Log feed** rather than re-crawling.

### 1.5 Bulk download alternative

The National Archives runs a bulk-download site (alpha) with per-type/per-year ZIPs of CLML, Akoma Ntoso, XHTML and plaintext, e.g. `http://leggovuk.s3-website-eu-west-1.amazonaws.com/texts/enacted-epublished/akn/ukpga/2020/enacted-epublished-akn-ukpga-2020.zip`. Consider it for the initial backfill (far fewer requests), then use the API feeds for ongoing updates. Verify availability before relying on it; it is updated only periodically.

## 2. Folder Structure

Captured acts live under `data/acts/`, mirroring how judgments mirror the TNA URI:

```
data/acts/
├── index/                          # Atom-feed-derived listing stubs (page_*.json per type)
│   ├── ukpga_page_00001.json
│   └── ...
└── {type}/{year}/{number}.json     # One JSON file per Act
    e.g.
    ukpga/2021/1.json               # Pension Schemes Act 2021  (uri: ukpga/2021/1)
    asp/2005/12.json                # Smoking, Health and Social Care (Scotland) Act 2005
    ukpga/Edw7/2/41.json            # Regnal-year URIs (older Acts) map path segments 1:1
```

Rule: the file path is always the legislation URI path segments joined as directories, exactly like `_judgment_path()` in `worker.py`. The URI (e.g. `ukpga/2021/1`) is the primary key, stored as `legislation_uri`.

## 3. Capture Workflow (two-phase, like `worker.py`)

Implemented in `acts_worker.py`. Resumable state in `acts_cursor.txt` (gitignored).

```bash
python acts_worker.py                        # run / resume (ukpga only)
python acts_worker.py --types ukpga,asp,nia  # choose legislation types
python acts_worker.py --pages-only           # only build the index
python acts_worker.py --limit 10             # pilot: stop after N fetches
python acts_worker.py --uri ukpga/2021/1     # (re-)fetch specific acts
python acts_worker.py --skip-pdfs            # skip the PDF fallback
```

PDF fallback: when an Act's `/data.xml` is missing or is a metadata shell with no body text (scanned historical Acts), the worker saves a metadata-only JSON (`"format": "pdf_only"`) and downloads the print PDF to `data/acts/pdfs/{uri}.pdf`, recording it as `pdf_path`. Extracting text from those PDFs (OCR) is deliberately out of scope for now.

### Phase A — Indexing

1. For each type in scope, page through `https://www.legislation.gov.uk/{type}/data.feed?results-count=100`, following `<link rel="next">` until exhausted. (Alternative: iterate per-year lists `/{type}/{year}/data.feed` for cleaner resumability.)
2. Write each page of entries as a stub file to `data/acts/index/{type}_page_NNNNN.json`.

Stub record format:

```json
{
  "legislation_uri": "ukpga/2021/1",
  "legislation_type": "ukpga",
  "year": 2021,
  "number": 1,
  "title": "Pension Schemes Act 2021",
  "published_date": "2021-02-11",
  "updated_date": "2024-05-02",
  "html_url": "https://www.legislation.gov.uk/ukpga/2021/1",
  "xml_url": "https://www.legislation.gov.uk/ukpga/2021/1/data.xml"
}
```

### Phase B — Fetching

For each stub not yet fetched:

1. `GET {uri}/data.xml` (latest revised CLML; falls back to enacted automatically when no revised version exists).
2. `GET {uri}/resources/data.xml` for metadata if not fully present in the content response.
3. Parse CLML into the Act JSON schema below and write to `data/acts/{uri path}.json`.
4. Update `acts_cursor.txt`.

CLML parsing notes:

- Metadata lives in the `ukm:Metadata` element (Dublin Core + `ukm:` namespace): title, type, year, number, enactment date, extent, alternative formats, unapplied effects.
- Body structure: `Part` → `Chapter` → `Pblock` (cross-headings) → `P1group`/`P1` (sections) → `P2`/`P3` (subsections/paragraphs). Schedules are under `Schedules`.
- Preserve section numbering and headings — they are the units lawyers cite ("s. 3(1)(a)") and the units we chunk on for embeddings.
- Repealed/omitted provisions appear as placeholders; keep the marker text (e.g. ". . .") but flag the section `"repealed": true` where CLML indicates it.
- Amendment annotations (`CommentaryRef` / commentary blocks) should be **excluded from `full_text`** but may be counted into `amendment_note_count`.

## 4. Act JSON Schema

One file per Act. Field order matters for readability: identity → status → contents → text.

```json
{
  "legislation_uri": "ukpga/2021/1",
  "legislation_type": "ukpga",
  "year": 2021,
  "number": 1,
  "title": "Pension Schemes Act 2021",
  "long_title": "An Act to make provision about pension schemes.",
  "version_captured": "current",
  "version_date": null,
  "enactment_date": "2021-02-11",
  "extent": ["E", "W", "S", "NI"],
  "status": "in_force",
  "has_unapplied_effects": false,
  "format": "xml",
  "contents": [
    { "level": "part", "number": "1", "heading": "Collective money purchase benefits" },
    { "level": "section", "number": "1", "heading": "Collective money purchase benefits and schemes", "parent": "part-1" }
  ],
  "sections": [
    {
      "id": "section-1",
      "number": "1",
      "heading": "Collective money purchase benefits and schemes",
      "part": "Part 1",
      "repealed": false,
      "text": "(1) For the purposes of this Part, a benefit provided under a pension scheme is a \"collective money purchase benefit\" if ..."
    }
  ],
  "schedules": [
    { "id": "schedule-1", "number": "1", "heading": "Collective money purchase benefits", "text": "..." }
  ],
  "full_text": "Plain text of the whole Act, sections and schedules concatenated in order.",
  "html_url": "https://www.legislation.gov.uk/ukpga/2021/1",
  "xml_url": "https://www.legislation.gov.uk/ukpga/2021/1/data.xml",
  "fetched_at": "2026-07-05T00:00:00Z"
}
```

Field rules:

- `legislation_uri` — **required**, primary key, drives the file path. Never rewrite it.
- `status` — one of `in_force`, `partially_in_force`, `prospective`, `repealed`, `unknown`. Derive from CLML metadata/restrict attributes; use `unknown` rather than guessing.
- `extent` — subset of `["E", "W", "S", "NI"]` (England, Wales, Scotland, Northern Ireland), from `RestrictExtent`.
- `sections[].text` — plain text with subsection numbering preserved inline. This is the chunking unit for embeddings (see `ACTS_INDEXING_README.md`).
- `full_text` — cap at ~2 MB; very large consolidated Acts should rely on `sections` and keep `full_text` truncated with a `"full_text_truncated": true` flag.
- `format: "pdf_only"` records with no XML get all identity/metadata fields plus `pdf_url`, and empty `sections`/`full_text`.
- Timestamps ISO 8601 UTC. Dates `YYYY-MM-DD`.
- Validate every file as JSON after writing.

## 5. Enrichment (later phase, optional)

Follow the judgment enrichment pattern (`ENRICHMENT_README.md`): enrichment is written **into the Act JSON file itself**, tracked in a new `acts_enrichment_manifest.json` with statuses `done` / `needs_review` / `failed`. Planned fields, inserted after `status` and before `contents`:

- `short_description` — one-paragraph plain-English explanation of what the Act does.
- `area_of_law` — broad categories aligned with the judgment taxonomy so Acts and judgments filter together.
- `key_provisions` — the handful of sections practitioners actually use, with one-line explanations.
- `related_acts` — predecessor/successor and closely related Acts by `legislation_uri`.
- `index_terms`, `catchwords` — same conventions as judgments.
- `confidence` — `{ score, level, notes }`.

Do not invent commencement dates, extents, or amendment status — these must come from source metadata only.

## 6. Update Strategy

1. Initial backfill: bulk site if available, otherwise feed-driven crawl within fair-use limits. The `ukpga` feed reports **12,020 items** total (verified 2026-07-04 via `leg:facetType`); a large share of the pre-1988 items are PDF-only, so the XML-bearing subset is smaller. At 1–2 req/s the full Phase 1 crawl (index + ~2 requests per Act) fits in well under a day and stays far below the 3,000-per-5-minutes limit.
2. Ongoing: poll `https://www.legislation.gov.uk/new/data.feed` and the Publication Log daily; re-fetch any Act whose revised version was republished (compare Atom `updated` against stored `fetched_at`).
3. Re-fetching overwrites the source fields but must preserve any enrichment fields already present in the file (same in-place merge discipline as `enrichment_worker.py`).

## 7. Cross-linking with Judgments

Judgments already carry `statutes_considered` (title + provisions) and the app has a `judgment_statutes` table. Once acts are imported, link `judgment_statutes.title` → `acts.title` (normalised: strip year suffix variations, match on title + year) so a judgment page can deep-link to the exact Act and section, and an Act page can list judgments that considered it. Matching rules and the DB side of this live in `ACTS_INDEXING_README.md`.
