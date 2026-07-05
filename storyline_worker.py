#!/usr/bin/env python3
"""Apply storyline fields to judgment JSON files and update storyline_manifest.json."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
MANIFEST_PATH = ROOT / "storyline_manifest.json"
CATCHUP_MANIFEST_PATH = ROOT / "storyline_catchup_manifest.json"
STORYLINE_FIELD = "storyline"
REQUIRED_STORYLINE_KEYS = [
    "title",
    "summary",
    "span",
    "parties",
    "stages",
    "turning_points",
    "confidence",
]


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _update_catchup_manifest(
    source_path: str,
    *,
    status: str,
    batch_number: int | None = None,
    notes: str = "",
) -> None:
    if not CATCHUP_MANIFEST_PATH.exists():
        return

    manifest = json.loads(CATCHUP_MANIFEST_PATH.read_text(encoding="utf-8"))
    for item in manifest.get("items", []):
        if item.get("source_path") != source_path:
            continue
        item["status"] = status
        item["storylined_at"] = date.today().isoformat()
        if batch_number is not None:
            item["batch_number"] = batch_number
        if notes:
            item["notes"] = notes
        break

    counts: dict[str, int] = {}
    for item in manifest.get("items", []):
        status_key = item.get("status", "pending")
        counts[status_key] = counts.get(status_key, 0) + 1
    manifest["stats"] = {
        "total": len(manifest.get("items", [])),
        "pending": counts.get("pending", 0),
        "done": counts.get("done", 0),
        "needs_review": counts.get("needs_review", 0),
        "failed": counts.get("failed", 0),
    }
    if batch_number is not None and manifest.get("next_batch") == batch_number:
        manifest["next_batch"] = batch_number + 1
    CATCHUP_MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_storyline(storyline: dict) -> None:
    missing = [key for key in REQUIRED_STORYLINE_KEYS if key not in storyline]
    if missing:
        raise ValueError(f"Missing storyline keys: {', '.join(missing)}")
    if not isinstance(storyline.get("stages"), list) or not storyline["stages"]:
        raise ValueError("storyline.stages must be a non-empty array")


def apply_storyline(
    source_path: str,
    storyline: dict,
    *,
    status: str = "done",
    notes: str = "",
    batch_number: int | None = None,
) -> None:
    validate_storyline(storyline)

    judgment_path = ROOT / source_path
    data = json.loads(judgment_path.read_text(encoding="utf-8"))
    base = {key: value for key, value in data.items() if key != STORYLINE_FIELD}

    new_data: dict = {}
    inserted = False
    for key, value in base.items():
        new_data[key] = value
        if not inserted and key == "full_text":
            new_data[STORYLINE_FIELD] = storyline
            inserted = True

    if not inserted:
        new_data[STORYLINE_FIELD] = storyline

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
            "stage_count": len(storyline.get("stages", [])),
            "storylined_at": date.today().isoformat(),
            "notes": notes or "Automated storyline batch.",
        }
    )
    manifest["records"] = records
    save_manifest(manifest)
    _update_catchup_manifest(source_path, status=status, batch_number=batch_number, notes=notes)


def _infer_batch_number(batch_path: Path | None, notes: str) -> int | None:
    if batch_path:
        match = re.search(r"catchup_batch_(\d+)", batch_path.name)
        if match:
            return int(match.group(1))
    match = re.search(r"Catchup batch (\d+)", notes)
    return int(match.group(1)) if match else None


def _normalize_batch_item(item: dict) -> tuple[str, dict, str, str]:
    source_path = item["source_path"]
    status = item.get("status", "done")
    notes = item.get("notes", "Automated storyline batch.")
    if STORYLINE_FIELD in item:
        storyline = item[STORYLINE_FIELD]
    else:
        storyline = {key: item[key] for key in REQUIRED_STORYLINE_KEYS}
    return source_path, storyline, status, notes


def apply_batch(batch_path: Path) -> int:
    raw = json.loads(batch_path.read_text(encoding="utf-8"))
    items = raw["judgments"] if isinstance(raw, dict) and "judgments" in raw else raw
    count = 0
    for item in items:
        source_path, storyline, status, notes = _normalize_batch_item(item)
        batch_number = _infer_batch_number(batch_path, notes)
        apply_storyline(
            source_path,
            storyline,
            status=status,
            notes=notes,
            batch_number=batch_number,
        )
        count += 1
    return count


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python storyline_worker.py <batch.json>", file=sys.stderr)
        sys.exit(1)
    count = apply_batch(Path(sys.argv[1]))
    print(f"Applied storyline to {count} judgments")


if __name__ == "__main__":
    main()
