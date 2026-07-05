# Judgment Storyline Guide

Storyline is a **second enrichment layer** applied only to judgments that already carry the base enrichment fields (`short_title`, `ratio`, etc.). It adds a structured narrative timeline so users can follow how a case unfolded — key events, institutional decisions, hearings, and turning points.

Storyline is written directly into each judgment JSON file. Do not write storyline results to the application database during this process.

## Prerequisite

A judgment must already appear in `enrichment_manifest.json` with `"status": "done"` (or `"needs_review"`) before storyline work begins. Storyline builds on the existing enrichment; it does not replace it.

## Tracking Progress

Use `storyline_manifest.json` as the marker for completed work.

Before storylining a judgment:

1. Open `storyline_manifest.json`.
2. Check whether the judgment's `source_path` is already listed with `"status": "done"`.
3. If it is already done, skip it.
4. If it is not done, add the `storyline` object to the judgment JSON and append a manifest record.

Use these status values:

- `done`: storyline was added and the JSON was validated.
- `needs_review`: storyline was added but should be checked by a human.
- `failed`: storyline could not be completed; include the reason in `notes`.

## The `storyline` Field (JSONB-shaped object)

Add a top-level `storyline` object to the judgment JSON, after the base enrichment fields and before `full_text`:

```json
{
  "storyline": {
    "title": "Short narrative headline for the case journey",
    "summary": "Two or three sentences describing the arc from dispute to resolution.",
    "span": {
      "start": "YYYY-MM-DD or null",
      "end": "YYYY-MM-DD or null",
      "label": "Human-readable date range, e.g. June 2000 – January 2001"
    },
    "parties": [
      {
        "role": "claimant | defendant | appellant | respondent | court | authority",
        "name": "Party or institution name",
        "short_name": "Optional abbreviation used in stage labels"
      }
    ],
    "stages": [
      {
        "id": "unique-stage-id",
        "order": 1,
        "date": "YYYY-MM-DD or null",
        "date_label": "Display label when date is partial, e.g. 'Early July 2000'",
        "date_precision": "exact | month | year | approximate | unknown",
        "title": "Short stage headline",
        "category": "background | factual | institutional | procedural | hearing | decision | outcome",
        "actor": "Who acted or decided at this stage",
        "what_happened": "Plain-English description of what occurred.",
        "why_it_matters": "Why this stage matters to the overall case.",
        "legal_hook": "Optional statute, rule, or procedural step engaged."
      }
    ],
    "turning_points": [
      {
        "stage_id": "id of the pivotal stage",
        "label": "One-line label for the turning point",
        "impact": "How this moment changed the direction of the case."
      }
    ],
    "confidence": {
      "score": 0.0,
      "level": "high | medium | low",
      "notes": ["Optional array of provenance or quality notes."]
    }
  }
}
```

### Stage categories

| Category | Use for |
|---|---|
| `background` | Pre-dispute context (e.g. parties' situation before the claim) |
| `factual` | Events that shaped the dispute but are not court/authority decisions |
| `institutional` | Decisions by public bodies, agencies, or officials outside court |
| `procedural` | Court process steps (permission, undertakings, adjournments) |
| `hearing` | Substantive court hearings or judgments at any level |
| `decision` | A binding or significant ruling (can overlap with `hearing`) |
| `outcome` | Final disposition and aftermath |

### Storyline quality rules

- Write for lawyers who want to **scan the case journey** before reading the full judgment.
- Stages must follow **chronological order** (`order` starting at 1).
- Use dates from the judgment where stated; use `date_precision` honestly — do not invent exact dates.
- `what_happened` should be factual; `why_it_matters` should explain significance.
- Do not invent parties, dates, or outcomes not supported by the source.
- Preserve all existing fields; do not truncate `full_text`.
- Validate the file as JSON after editing.

## Manifest Record Format

After storylining a file, append a record like this to `storyline_manifest.json`:

```json
{
  "source_path": "data/judgments/ewca/civ/2001/540.json",
  "tna_uri": "ewca/civ/2001/540",
  "neutral_citation": "[2001] EWCA Civ 540",
  "status": "done",
  "stage_count": 14,
  "storylined_at": "YYYY-MM-DD",
  "notes": "Short note about the storyline run."
}
```

## Where Storyline Lives

Storyline must be written **into the original judgment JSON file** under `data/judgments/`. Do not create separate sidecar files.

The `storyline_batches/` JSON files are optional staging inputs for `storyline_worker.py`. The canonical record is always the source judgment file itself.

## Applying a Batch

```bash
python storyline_worker.py storyline_batches/batch_01.json
```

Each batch item should contain `source_path`, optional `status` and `notes`, and either:

- a `storyline` object with the full structure above, or
- the storyline fields directly on the item under `storyline`.

## Current Pilot

The first storylined source file is:

`data/judgments/ewca/civ/2001/540.json`

This is also the first entry in `enrichment_manifest.json`.

## Catchup backfill

For judgments enriched before storyline existed, use `STORYLINE_CATCHUP_README.md` and `storyline_catchup_manifest.json`.
