#!/usr/bin/env python3
"""Temporary catchup tracker for storyline backfill on pre-enriched judgments."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
ENRICHMENT_MANIFEST = ROOT / "enrichment_manifest.json"
STORYLINE_MANIFEST = ROOT / "storyline_manifest.json"
CATCHUP_MANIFEST = ROOT / "storyline_catchup_manifest.json"
DONE_STATUSES = {"done", "needs_review"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compute_stats(items: list[dict]) -> dict:
    counts = Counter(item.get("status", "pending") for item in items)
    return {
        "total": len(items),
        "pending": counts.get("pending", 0),
        "done": counts.get("done", 0),
        "needs_review": counts.get("needs_review", 0),
        "failed": counts.get("failed", 0),
    }


def _max_existing_batch_number() -> int:
    """Highest catchup_batch_NN.json already written, so numbering never collides."""
    batch_dir = ROOT / "storyline_batches"
    highest = 0
    if batch_dir.exists():
        for path in batch_dir.glob("catchup_batch_*.json"):
            match = re.search(r"catchup_batch_(\d+)", path.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return highest


def init_catchup() -> None:
    """Build (or refresh) the catchup manifest.

    Idempotent: re-running preserves non-pending statuses, created_at, and
    next_batch from any existing manifest, and only adds newly-eligible items.
    """
    enrichment = load_json(ENRICHMENT_MANIFEST)
    storylined = set()
    if STORYLINE_MANIFEST.exists():
        storyline = load_json(STORYLINE_MANIFEST)
        storylined = {
            record["source_path"]
            for record in storyline.get("records", [])
            if record.get("status") in DONE_STATUSES
        }

    previous_items: dict[str, dict] = {}
    previous_next_batch = 1
    created_at = date.today().isoformat()
    if CATCHUP_MANIFEST.exists():
        previous = load_json(CATCHUP_MANIFEST)
        previous_items = {item["source_path"]: item for item in previous.get("items", [])}
        previous_next_batch = previous.get("next_batch", 1)
        created_at = previous.get("created_at", created_at)

    items: list[dict] = []
    for record in enrichment.get("records", []):
        if record.get("status") not in DONE_STATUSES:
            continue
        source_path = record["source_path"]
        if source_path in storylined:
            continue
        item = {
            "source_path": source_path,
            "tna_uri": record.get("tna_uri"),
            "neutral_citation": record.get("neutral_citation"),
            "status": "pending",
            "batch_number": None,
            "storylined_at": None,
            "notes": None,
        }
        prev = previous_items.get(source_path)
        if prev and prev.get("status") != "pending":
            item["status"] = prev["status"]
            item["batch_number"] = prev.get("batch_number")
            item["storylined_at"] = prev.get("storylined_at")
            item["notes"] = prev.get("notes")
        items.append(item)

    items.sort(key=lambda item: item["source_path"])
    next_batch = max(previous_next_batch, _max_existing_batch_number() + 1)
    manifest = {
        "schema_version": 1,
        "purpose": (
            "Temporary catchup tracker for storyline backfill on judgments already "
            "enriched before storyline became mandatory. Archive or delete when complete."
        ),
        "created_at": created_at,
        "batch_size": 10,
        "next_batch": next_batch,
        "status_values": ["pending", "done", "needs_review", "failed"],
        "stats": compute_stats(items),
        "items": items,
    }
    save_json(CATCHUP_MANIFEST, manifest)
    stats = manifest["stats"]
    print(
        f"Catchup manifest ready: {stats['total']} items "
        f"({stats['pending']} pending, {stats['done']} done, "
        f"{stats['failed']} failed) · next batch {next_batch}."
    )


def show_status() -> None:
    if not CATCHUP_MANIFEST.exists():
        print("Catchup manifest not found. Run: python storyline_catchup.py init")
        sys.exit(1)
    manifest = load_json(CATCHUP_MANIFEST)
    stats = manifest.get("stats") or compute_stats(manifest.get("items", []))
    print(json.dumps({"next_batch": manifest.get("next_batch"), "stats": stats}, indent=2))


def next_pending(limit: int) -> list[dict]:
    if not CATCHUP_MANIFEST.exists():
        raise FileNotFoundError("Catchup manifest not found. Run init first.")
    manifest = load_json(CATCHUP_MANIFEST)
    pending = [item for item in manifest.get("items", []) if item.get("status") == "pending"]
    return pending[:limit]


def mark_items(
    updates: list[dict],
    *,
    batch_number: int | None = None,
    default_status: str = "done",
) -> None:
    if not CATCHUP_MANIFEST.exists():
        return
    manifest = load_json(CATCHUP_MANIFEST)
    by_path = {item["source_path"]: item for item in manifest.get("items", [])}
    for update in updates:
        source_path = update["source_path"]
        item = by_path.get(source_path)
        if not item:
            continue
        item["status"] = update.get("status", default_status)
        item["storylined_at"] = update.get("storylined_at", date.today().isoformat())
        if batch_number is not None:
            item["batch_number"] = batch_number
        if update.get("notes"):
            item["notes"] = update["notes"]
    manifest["stats"] = compute_stats(manifest["items"])
    if batch_number is not None and manifest.get("next_batch") == batch_number:
        manifest["next_batch"] = batch_number + 1
    save_json(CATCHUP_MANIFEST, manifest)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python storyline_catchup.py <init|status>", file=sys.stderr)
        sys.exit(1)
    command = sys.argv[1]
    if command == "init":
        init_catchup()
    elif command == "status":
        show_status()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
