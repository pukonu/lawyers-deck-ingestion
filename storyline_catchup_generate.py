#!/usr/bin/env python3
"""Self-batching storyline catchup runner.

Reads pending judgments from storyline_catchup_manifest.json, generates
storylines via the Gemini API, and applies them batch by batch in a loop.
Batch numbering comes from the manifest's `next_batch` — no arguments needed.

Usage:
  python storyline_catchup_generate.py                 # loop until all pending done
  python storyline_catchup_generate.py --max-batches 1 # run a single batch
  python storyline_catchup_generate.py --size 10       # override batch size

Resumable: progress is tracked in the catchup manifest after every batch, so
the script can be stopped and restarted at any time.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from storyline_catchup import mark_items
from storyline_worker import apply_batch

ROOT = Path(__file__).parent
CATCHUP_MANIFEST = ROOT / "storyline_catchup_manifest.json"
BATCH_DIR = ROOT / "storyline_batches"
ENV_FILE = ROOT.parent / ".env"

SYSTEM_PROMPT = (
    "You are a legal editor creating structured case timelines for UK judgments. "
    "Write in plain British English for practising lawyers. "
    "Use only facts supported by the provided judgment context. "
    "Return valid JSON only."
)


def load_env() -> None:
    """Load GEMINI_* vars from app/.env if not already set (no dependency on dotenv)."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def load_manifest() -> dict:
    if not CATCHUP_MANIFEST.exists():
        raise FileNotFoundError(
            "Catchup manifest not found. Run: python storyline_catchup.py init"
        )
    return json.loads(CATCHUP_MANIFEST.read_text(encoding="utf-8"))


def truncate(text: str, max_len: int = 14000) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n\n[truncated for generation]"


def build_prompt(judgment: dict) -> str:
    context = {
        "tna_uri": judgment.get("tna_uri"),
        "case_name": judgment.get("case_name"),
        "neutral_citation": judgment.get("neutral_citation"),
        "court": judgment.get("court"),
        "division": judgment.get("division"),
        "date_handed_down": judgment.get("date_handed_down"),
        "summary": judgment.get("summary"),
        "short_title": judgment.get("short_title"),
        "procedural_posture": judgment.get("procedural_posture"),
        "outcome": judgment.get("outcome"),
        "ratio": judgment.get("ratio"),
        "key_facts": judgment.get("key_facts"),
        "legal_issues": judgment.get("legal_issues"),
        "area_of_law": judgment.get("area_of_law"),
        "linked_authorities": judgment.get("linked_authorities"),
        "full_text_excerpt": truncate(judgment.get("full_text") or ""),
    }
    return (
        "Create a storyline object for this enriched UK judgment.\n"
        "Return JSON with this exact top-level shape:\n"
        '{ "storyline": { "title", "summary", "span", "parties", "stages", "turning_points", "confidence" } }\n\n'
        "Rules:\n"
        "- stages must be chronological with order starting at 1\n"
        "- each stage needs: id, order, date, date_label, date_precision, title, category, actor, what_happened, why_it_matters, legal_hook\n"
        "- category must be one of: background, factual, institutional, procedural, hearing, decision, outcome\n"
        "- date_precision must be one of: exact, month, year, approximate, unknown\n"
        "- include 6-16 stages where supported\n"
        "- include 2-5 turning_points referencing stage_id values\n"
        "- confidence.notes must be an array of strings\n"
        "- do not invent parties, dates, or outcomes\n\n"
        f"Judgment context:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def generate_storyline(judgment: dict) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured (set it in app/.env)")

    model = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={urllib.parse.quote(api_key)}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": build_prompt(judgment)}]}],
        "generationConfig": {
            "temperature": 0.2,
            # Generous cap: thinking models spend output tokens on reasoning
            # before the JSON, and 4096 was truncating storylines mid-string.
            "maxOutputTokens": 32768,
            "responseMimeType": "application/json",
        },
    }

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as res:
                body = json.loads(res.read().decode("utf-8"))
            candidate = body.get("candidates", [{}])[0]
            finish_reason = candidate.get("finishReason")
            parts = candidate.get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts).strip()
            if not text:
                raise RuntimeError(f"Gemini returned empty content (finishReason={finish_reason})")
            if finish_reason == "MAX_TOKENS":
                raise RuntimeError("Gemini output truncated at token limit")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                start = text.find("{")
                end = text.rfind("}")
                if start == -1 or end == -1:
                    raise
                parsed = json.loads(text[start : end + 1])
            storyline = parsed.get("storyline")
            if not isinstance(storyline, dict) or not storyline.get("stages"):
                raise RuntimeError("Gemini response missing storyline.stages")
            return storyline
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < 3:
                time.sleep(attempt * 2)
    raise last_error or RuntimeError("Generation failed")


def run_one_batch(size: int) -> tuple[int, int, bool]:
    """Generate + apply one batch. Returns (succeeded, failed, more_pending)."""
    manifest = load_manifest()
    batch = manifest.get("next_batch", 1)
    pending = [item for item in manifest.get("items", []) if item.get("status") == "pending"]
    selected = pending[:size]
    if not selected:
        return 0, 0, False

    batch_name = f"catchup_batch_{batch:02d}.json"
    batch_path = BATCH_DIR / batch_name
    judgments: list[dict] = []
    failed: list[dict] = []

    print(f"— Batch {batch}: generating {len(selected)} storyline(s) "
          f"({len(pending)} pending overall)")
    for index, item in enumerate(selected, start=1):
        label = item.get("neutral_citation") or item.get("tna_uri")
        print(f"  [{index}/{len(selected)}] {label}")
        try:
            file_path = ROOT / item["source_path"]
            source = json.loads(file_path.read_text(encoding="utf-8"))
            storyline = generate_storyline(source)
            judgments.append(
                {
                    "source_path": item["source_path"],
                    "status": "done",
                    "notes": f"Catchup batch {batch} generated via storyline_catchup_generate.py",
                    "storyline": storyline,
                }
            )
        except Exception as exc:  # noqa: BLE001
            print(f"    ✗ failed: {exc}")
            failed.append(
                {
                    "source_path": item["source_path"],
                    "status": "failed",
                    "notes": f"Catchup batch {batch}: {exc}",
                }
            )

    # Mark failures so the loop moves past them instead of retrying forever.
    if failed:
        mark_items(failed, batch_number=batch, default_status="failed")

    if not judgments:
        print("  No storylines generated in this batch.")
        return 0, len(failed), True

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    batch_path.write_text(
        json.dumps({"judgments": judgments}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    applied = apply_batch(batch_path)
    print(f"  Applied {applied} storyline(s) from {batch_name}")

    remaining = load_manifest()["stats"]["pending"]
    return len(judgments), len(failed), remaining > 0


def main() -> None:
    load_env()

    argv = sys.argv[1:]

    def arg_value(flag: str, default: int) -> int:
        return int(argv[argv.index(flag) + 1]) if flag in argv else default

    size = arg_value("--size", 10)
    max_batches = arg_value("--max-batches", 0)  # 0 = run until nothing pending

    total_done = 0
    total_failed = 0
    batches_run = 0

    while True:
        succeeded, failed, more_pending = run_one_batch(size)
        total_done += succeeded
        total_failed += failed
        if succeeded or failed:
            batches_run += 1

        if not more_pending:
            print("All pending judgments processed.")
            break
        if max_batches and batches_run >= max_batches:
            break
        if not succeeded and failed:
            print("Entire batch failed — stopping so the failure can be investigated.")
            break

    stats = load_manifest()["stats"]
    print(
        f"\nRun summary: {batches_run} batch(es), {total_done} done, {total_failed} failed. "
        f"Overall: {stats['done']} done / {stats['pending']} pending / {stats['failed']} failed."
    )


if __name__ == "__main__":
    main()
