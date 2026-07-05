#!/usr/bin/env python3
"""Apply enrichment fields to judgment JSON files and update enrichment_manifest.json."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "enrichment_manifest.json"
REQUIRED_FIELDS = [
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
]


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_enrichment(source_path: str, enrichment: dict, *, status: str = "done", notes: str = "") -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in enrichment]
    if missing:
        raise ValueError(f"Missing enrichment fields: {', '.join(missing)}")

    judgment_path = ROOT / source_path
    data = json.loads(judgment_path.read_text(encoding="utf-8"))
    base = {key: value for key, value in data.items() if key not in REQUIRED_FIELDS}

    new_data: dict = {}
    inserted = False
    for key, value in base.items():
        if not inserted and key == "full_text":
            for field in REQUIRED_FIELDS:
                new_data[field] = enrichment[field]
            inserted = True
        new_data[key] = value
        if not inserted and key == "summary":
            for field in REQUIRED_FIELDS:
                new_data[field] = enrichment[field]
            inserted = True

    if not inserted:
        for field in REQUIRED_FIELDS:
            new_data[field] = enrichment[field]

    judgment_path.write_text(json.dumps(new_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    json.loads(judgment_path.read_text(encoding="utf-8"))

    manifest = load_manifest()
    records = manifest.setdefault("records", [])
    records = [r for r in records if r.get("source_path") != source_path]
    records.append(
        {
            "source_path": source_path,
            "tna_uri": data.get("tna_uri"),
            "neutral_citation": data.get("neutral_citation"),
            "status": status,
            "enriched_fields": REQUIRED_FIELDS.copy(),
            "enriched_at": date.today().isoformat(),
            "notes": notes or "Automated enrichment batch.",
        }
    )
    manifest["records"] = records
    save_manifest(manifest)


def _normalize_batch_item(item: dict) -> tuple[str, dict, str, str]:
    source_path = item["source_path"]
    status = item.get("status", "done")
    notes = item.get("notes", "Automated enrichment batch.")
    if "enrichment" in item:
        enrichment = item["enrichment"]
    else:
        enrichment = {field: item[field] for field in REQUIRED_FIELDS}
    return source_path, enrichment, status, notes


def apply_batch(batch_path: Path) -> int:
    raw = json.loads(batch_path.read_text(encoding="utf-8"))
    items = raw["judgments"] if isinstance(raw, dict) and "judgments" in raw else raw
    count = 0
    for item in items:
        source_path, enrichment, status, notes = _normalize_batch_item(item)
        apply_enrichment(source_path, enrichment, status=status, notes=notes)
        count += 1
    return count


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python enrichment_worker.py <batch.json>", file=sys.stderr)
        sys.exit(1)
    count = apply_batch(Path(sys.argv[1]))
    print(f"Applied enrichment to {count} judgments")


if __name__ == "__main__":
    main()
