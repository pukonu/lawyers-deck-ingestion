# Storyline Catchup Guide

This is a **temporary backfill workflow** for judgments that were enriched before `storyline` became mandatory.

Use `storyline_catchup_manifest.json` as the resumable catchup index. When all items are `done` or `needs_review`, archive or delete this manifest.

## Why this exists

- `enrichment_manifest.json` tracks ~5,000 enriched judgments
- `storyline_manifest.json` tracks storyline completion
- The catchup manifest lists every enriched judgment that still lacks storyline

## One-time setup

```bash
cd app
make storyline-catchup-init
```

This builds `storyline_catchup_manifest.json` from:

- all `done` / `needs_review` rows in `enrichment_manifest.json`
- minus judgments already listed in `storyline_manifest.json`

## Check progress

```bash
make storyline-catchup-status
```

## Run the catchup (self-batching loop)

The runner batches by itself in a loop — no batch number needed. It reads
`next_batch` from the manifest, generates a batch, applies it, updates the
index, and moves on to the next batch until nothing is pending:

```bash
make storyline-catchup
```

Batch size defaults to 10; override with `CATCHUP_SIZE`:

```bash
make storyline-catchup CATCHUP_SIZE=20
```

Requires `GEMINI_API_KEY` in `app/.env` (loaded automatically by the script).

## Run a single batch (the regular one)

To process just one batch and stop — useful for supervised runs:

```bash
make storyline-catchup-batch
```

Or directly:

```bash
cd ingestion && python storyline_catchup_generate.py --max-batches 1
```

## Continue later

Stop the loop at any time (Ctrl-C). Progress is saved to the manifest after
every batch, so simply re-run to continue where it left off:

```bash
make storyline-catchup
```

Judgments that fail generation are marked `failed` with the error in `notes`
and are skipped on subsequent runs — review them with `make storyline-catchup-status`.

## Push storylines to the database

After JSON files are updated, push to Postgres per judgment or in bulk:

```bash
make db-import-storyline TNA_URI=ewca/civ/2002/215
```

For large DB backfills, add a dedicated import pass later. File-level catchup is the priority here.

## Batch files

Generated catchup batches live in:

`storyline_batches/catchup_batch_01.json`, `catchup_batch_02.json`, ...

These are staging inputs for `storyline_worker.py`, just like normal storyline batches.

## Status values

| Status | Meaning |
|---|---|
| `pending` | Enriched but storyline not yet written |
| `done` | Storyline applied to JSON and recorded in manifests |
| `needs_review` | Storyline added but should be checked by a human |
| `failed` | Could not complete; see `notes` |

## When catchup is complete

1. Confirm `make storyline-catchup-status` shows `pending: 0`
2. Archive or delete `storyline_catchup_manifest.json`
3. Continue using `storyline_manifest.json` for all new work

## Future enrichment

New judgments must include storyline as part of the full enrichment pass. See the **Storyline (required for complete enrichment)** section in `ENRICHMENT_README.md`.
