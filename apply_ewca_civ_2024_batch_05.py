#!/usr/bin/env python3
"""Apply manual batch 05 enrichment and storyline for ten EWCA Civ 2024 judgments."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BATCH_FILE = ROOT / "storyline_batches" / "ewca_civ_2024_batch_05.json"
JUDGMENTS_ROOT = ROOT / "data" / "judgments"
ENRICHMENT_MANIFEST = ROOT / "enrichment_manifest.json"
STORYLINE_MANIFEST = ROOT / "storyline_manifest.json"

BATCH_NUMBER = 5
BATCH_DATE = "2026-07-07"
NOTES = "Manual batch 05 enrichment and storyline, 2026-07-07."

ENRICHMENT_FIELDS = [
    "short_title",
    "area_of_law",
    "statutes_considered",
    "key_facts",
    "procedural_posture",
    "outcome",
    "ratio",
    "legal_issues",
    "catchwords",
    "index_terms",
    "linked_authorities",
    "confidence",
    "storyline",
]

CASES: list[dict] = json.loads(
    Path(__file__).with_name("ewca_civ_2024_batch_05_cases.json").read_text(encoding="utf-8")
)


def validate_json_text(text: str) -> None:
    json.loads(text)


def apply_to_judgment(source_path: str, judges: list[str], enrichment: dict) -> None:
    missing = [f for f in ENRICHMENT_FIELDS if f not in enrichment]
    if missing:
        raise ValueError(f"Missing enrichment fields in {source_path}: {', '.join(missing)}")

    judgment_path = ROOT / source_path
    data = json.loads(judgment_path.read_text(encoding="utf-8"))
    full_text = data.get("full_text")
    if not full_text or len(full_text) < 100:
        raise ValueError(f"full_text missing or truncated in {source_path}")

    base = {k: v for k, v in data.items() if k not in ENRICHMENT_FIELDS and k != "judges"}
    new_data: dict = {}
    inserted = False
    for key, value in base.items():
        if not inserted and key == "full_text":
            for field in ENRICHMENT_FIELDS:
                new_data[field] = enrichment[field]
            inserted = True
        new_data[key] = value
        if not inserted and key == "summary":
            for field in ENRICHMENT_FIELDS:
                new_data[field] = enrichment[field]
            inserted = True

    if not inserted:
        for field in ENRICHMENT_FIELDS:
            new_data[field] = enrichment[field]

    new_data["judges"] = judges
    out_text = json.dumps(new_data, ensure_ascii=False, indent=2) + "\n"
    validate_json_text(out_text)
    written = json.loads(out_text)
    if written.get("full_text") != full_text:
        raise ValueError(f"full_text changed in {source_path}")
    judgment_path.write_text(out_text, encoding="utf-8")


def write_batch_manifest(cases: list[dict]) -> None:
    BATCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    enrichment_records = []
    storyline_records = []
    for case in cases:
        src = case["source_path"]
        enrichment_records.append(
            {
                "source_path": src,
                "enrichment": {k: case["enrichment"][k] for k in ENRICHMENT_FIELDS if k != "storyline"},
                "status": "done",
                "notes": NOTES,
            }
        )
        storyline_records.append(
            {
                "source_path": src,
                "storyline": case["enrichment"]["storyline"],
                "status": "done",
                "notes": NOTES,
            }
        )

    batch = {
        "batch_number": BATCH_NUMBER,
        "batch_date": BATCH_DATE,
        "notes": NOTES,
        "enrichment_records": enrichment_records,
        "storyline_records": storyline_records,
    }
    text = json.dumps(batch, ensure_ascii=False, indent=2) + "\n"
    validate_json_text(text)
    BATCH_FILE.write_text(text, encoding="utf-8")


def update_enrichment_manifest(records: list[dict]) -> None:
    manifest = json.loads(ENRICHMENT_MANIFEST.read_text(encoding="utf-8"))
    items = manifest.setdefault("records", [])
    for rec in records:
        src = rec["source_path"]
        items[:] = [r for r in items if r.get("source_path") != src]
        meta = json.loads((ROOT / src).read_text(encoding="utf-8"))
        items.append(
            {
                "source_path": src,
                "tna_uri": meta.get("tna_uri"),
                "neutral_citation": meta.get("neutral_citation"),
                "status": "done",
                "enriched_fields": ENRICHMENT_FIELDS.copy(),
                "enriched_at": BATCH_DATE,
                "notes": NOTES,
            }
        )
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    validate_json_text(text)
    ENRICHMENT_MANIFEST.write_text(text, encoding="utf-8")


def update_storyline_manifest(records: list[dict]) -> None:
    manifest = json.loads(STORYLINE_MANIFEST.read_text(encoding="utf-8"))
    items = manifest.setdefault("records", [])
    for rec in records:
        src = rec["source_path"]
        items[:] = [r for r in items if r.get("source_path") != src]
        meta = json.loads((ROOT / src).read_text(encoding="utf-8"))
        stage_count = len(rec.get("storyline", {}).get("stages", []))
        items.append(
            {
                "source_path": src,
                "tna_uri": meta.get("tna_uri"),
                "neutral_citation": meta.get("neutral_citation"),
                "status": "done",
                "stage_count": stage_count,
                "storylined_at": BATCH_DATE,
                "notes": NOTES,
            }
        )
    text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    validate_json_text(text)
    STORYLINE_MANIFEST.write_text(text, encoding="utf-8")


def validate_all(paths: list[Path]) -> None:
    for path in paths:
        subprocess.run(
            [sys.executable, "-m", "json.tool", str(path)],
            check=True,
            capture_output=True,
        )


def main() -> None:
    if len(CASES) != 10:
        raise RuntimeError(f"Expected 10 cases, got {len(CASES)}")

    write_batch_manifest(CASES)
    for case in CASES:
        apply_to_judgment(case["source_path"], case["judges"], case["enrichment"])

    batch = json.loads(BATCH_FILE.read_text(encoding="utf-8"))
    update_enrichment_manifest(batch["enrichment_records"])
    update_storyline_manifest(batch["storyline_records"])

    paths = [BATCH_FILE, ENRICHMENT_MANIFEST, STORYLINE_MANIFEST]
    paths += [ROOT / c["source_path"] for c in CASES]
    validate_all(paths)

    print(f"Applied batch {BATCH_NUMBER} to {len(CASES)} judgments")
    print(f"Batch manifest: {BATCH_FILE}")


if __name__ == "__main__":
    main()
