# Judgment Enrichment Guide

This folder contains captured judgment JSON files and the tracking metadata for enriching them. Enrichment is written directly into each judgment JSON file. Do not write enrichment results to the application database during this process.

## Tracking Progress

Use `enrichment_manifest.json` as the marker for completed work.

Before enriching a judgment:

1. Open `enrichment_manifest.json`.
2. Check whether the judgment's `source_path` is already listed with `"status": "done"`.
3. If it is already done, skip it.
4. If it is not done, enrich the judgment JSON file and then append a manifest record.

Use these status values:

- `done`: enrichment fields were added and the JSON was validated.
- `needs_review`: enrichment was added but should be checked by a human.
- `failed`: enrichment could not be completed; include the reason in `notes`.

## Required Enrichment Fields

Add these top-level fields to the judgment JSON, preferably after `summary` and before `full_text`:

- `short_title`: a concise lawyer-friendly title that explains what the case is about.
- `area_of_law`: broad legal categories for filtering and browsing.
- `statutes_considered`: structured list of Acts, statutory instruments, codes, or rules considered, with provisions where identifiable.
- `key_facts`: short factual points needed to understand the dispute and the court's decision.
- `procedural_posture`: how the case reached the court, e.g. appeal, judicial review, application, sentencing appeal.
- `outcome`: the result, e.g. appeal allowed, application dismissed, sentence reduced.
- `ratio`: the core legal rule or principle decided by the judgment, written in plain legal English.
- `legal_issues`: an array of the main legal issues.
- `catchwords`: short searchable legal topic labels.
- `index_terms`: broader terms for search, filtering, and future indexing.
- `linked_authorities`: cases or authorities materially discussed or relied on. Use an empty array if none are identified.
- `confidence`: structured confidence metadata for the enrichment, with `score`, `level`, and `notes`.

## Storyline (required for complete enrichment)

After the base enrichment fields above are added, every judgment must also receive a `storyline` object before the record is considered complete.

- Add `storyline` after the base enrichment fields and before `full_text`.
- Follow the schema and quality rules in `STORYLINE_README.md`.
- Track storyline completion in `storyline_manifest.json`.
- For judgments enriched before storyline existed, use the temporary catchup tracker in `STORYLINE_CATCHUP_README.md`.

A judgment is not fully enriched until both:

1. `enrichment_manifest.json` lists it as `done` or `needs_review`, and
2. `storyline_manifest.json` lists it as `done` or `needs_review`.

## Enrichment Quality

Write for lawyers who need to find and understand judgments quickly.

- Keep `short_title` specific, not generic.
- Keep `ratio` focused on the principle decided, not a general summary of the facts.
- Do not invent judges, dates, parties, citations, or authorities.
- Use `null` or an empty array only where the source judgment does not provide the information.
- Preserve existing source fields such as `tna_uri`, `case_name`, `neutral_citation`, `summary`, `full_text`, `html_url`, and `xml_url`.
- Do not delete or truncate `full_text`.
- Validate the file as JSON after editing.

## Manifest Record Format

After enriching a file, append a record like this to `enrichment_manifest.json`:

```json
{
  "source_path": "data/judgments/ewca/civ/2001/540.json",
  "tna_uri": "ewca/civ/2001/540",
  "neutral_citation": "[2001] EWCA Civ 540",
  "status": "done",
  "enriched_fields": [
    "area_of_law",
    "statutes_considered",
    "key_facts",
    "short_title",
    "procedural_posture",
    "outcome",
    "ratio",
    "legal_issues",
    "catchwords",
    "index_terms",
    "linked_authorities",
    "confidence",
    "storyline"
  ],
  "enriched_at": "YYYY-MM-DD",
  "notes": "Short note about the enrichment run."
}
```

## Where Enrichment Lives

Enrichment must be written **into the original judgment JSON file** under `data/judgments/`. Do not create separate enriched copies, sidecar files, or standalone index files for this workflow.

The `enrichment_batches/` JSON files are optional staging inputs for `enrichment_worker.py`. The canonical enriched record is always the source judgment file itself.

## Applying a Batch

To write enrichments into judgment files and update the manifest in one step:

```bash
python enrichment_worker.py enrichment_batches/batch_01.json
```

Each batch item should contain `source_path`, optional `status` and `notes`, and either:

- an `enrichment` object with all required fields, or
- the required fields directly on the item.

## Current Pilot

The first enriched source file is:

`data/judgments/ewca/civ/2001/540.json`

Batch files for the next 50 judgments live in `enrichment_batches/batch_01.json` through `batch_05.json`.
