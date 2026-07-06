#!/usr/bin/env python3
"""
Lawyers Deck — legislation.gov.uk UK Acts Ingestion Worker
==========================================================
Pulls UK Acts (primary legislation) from legislation.gov.uk and saves each
one as a JSON file under data/acts/{type}/{year}/{number}.json, resuming
via acts_cursor.txt. See ACTS_README.md for the full specification.

For each Act the worker requests the latest CLML XML (/data.xml). When an
Act has no XML (older Acts are PDF-only), it falls back to the metadata
resource (/resources/data.xml) and downloads the print PDF instead, saving
it under data/acts/pdfs/ and writing a metadata-only JSON stub with
format="pdf_only".

Usage
-----
  python acts_worker.py                        # run / resume (ukpga only)
  python acts_worker.py --types ukpga,asp,nia  # choose legislation types
  python acts_worker.py --reset                # start over
  python acts_worker.py --pages-only           # only build the index
  python acts_worker.py --limit 10             # stop after N fetches (pilot)
  python acts_worker.py --uri ukpga/2021/1     # fetch specific Act(s) only
  python acts_worker.py --skip-pdfs            # skip PDF download fallback
  python acts_worker.py --concurrency 3       # parallel requests (default: 3)
  python acts_worker.py --delay 0.5           # per-worker request delay
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from lxml import etree
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

# ─── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
ACTS_DIR = DATA_DIR / "acts"
ACTS_INDEX_DIR = ACTS_DIR / "index"
ACTS_PDF_DIR = ACTS_DIR / "pdfs"
CURSOR_FILE = ROOT / "acts_cursor.txt"

# ─── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://www.legislation.gov.uk"
HEADERS = {
    "User-Agent": "LawyersDeckIngestion/1.0 (+https://lawyersdeck.com; research)",
    "Accept-Language": "en-GB,en;q=0.9",
}
MAX_RETRIES = 4
REQUEST_TIMEOUT = 60.0
RESULTS_PER_PAGE = 100
MAX_FULL_TEXT_BYTES = 2_000_000  # ~2 MB cap per Act (see ACTS_README.md §4)

DEFAULT_TYPES = ["ukpga"]
KNOWN_TYPES = [
    "ukpga", "asp", "asc", "anaw", "nia", "ukla",
    "mwa", "mnia", "apgb", "aep", "aosp", "aip", "apni",
]

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "leg": "http://www.legislation.gov.uk/namespaces/legislation",
    "ukm": "http://www.legislation.gov.uk/namespaces/metadata",
    "dc": "http://purl.org/dc/elements/1.1/",
}

# Subtrees excluded from extracted text (amendment annotations etc.)
SKIP_SUBTREES = {"Commentaries", "CommentaryRef", "MarginNotes", "Versions", "Footnotes"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _local(tag) -> str:
    """Local name of an lxml tag (strips the namespace)."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


# ─── State / Cursor ───────────────────────────────────────────────────────────

@dataclass
class Cursor:
    phase: str = "indexing"           # "indexing" | "fetching" | "done"
    types: list[str] = field(default_factory=lambda: list(DEFAULT_TYPES))
    type_index: int = 0               # which type we're currently indexing
    index_page: int = 1               # next feed page for the current type
    total_acts: int = 0
    fetched: int = 0
    pdf_only: int = 0
    errors: int = 0
    skipped: int = 0
    started_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.started_at:
            self.started_at = _now()

    @classmethod
    def load(cls, path: Path) -> "Cursor":
        if path.exists():
            try:
                raw = json.loads(path.read_text())
                valid = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
                return cls(**valid)
            except Exception:
                pass
        return cls()

    def save(self, path: Path) -> None:
        self.updated_at = _now()
        path.write_text(json.dumps(asdict(self), indent=2))

    def reset(self, types: list[str]) -> None:
        self.phase = "indexing"
        self.types = types
        self.type_index = 0
        self.index_page = 1
        self.total_acts = 0
        self.fetched = 0
        self.pdf_only = 0
        self.errors = 0
        self.skipped = 0
        self.started_at = _now()
        self.updated_at = _now()


# ─── HTTP helper ──────────────────────────────────────────────────────────────

async def get(
    client: httpx.AsyncClient,
    url: str,
    sem: asyncio.Semaphore,
    delay: float,
    retries: int = MAX_RETRIES,
) -> Optional[httpx.Response]:
    """GET with fair-use pacing and backoff. Returns the response on 200, None otherwise."""
    async with sem:
        for attempt in range(retries):
            try:
                await asyncio.sleep(delay)
                r = await client.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                if r.status_code == 200:
                    return r
                if r.status_code == 404:
                    return None
                if r.status_code == 202:
                    # Dynamically generated resource (e.g. PDF) — wait and retry
                    await asyncio.sleep(12)
                elif r.status_code in (403, 429):
                    # Rate limited — back off hard per the Fair Use Policy
                    await asyncio.sleep(60 * (attempt + 1))
                elif r.status_code == 300:
                    # Ambiguous URI (old Acts sharing year/number) — cannot resolve here
                    return None
                elif r.status_code >= 500:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    return None
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError):
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
        return None


# ─── Atom feed parsing (Phase A) ──────────────────────────────────────────────

@dataclass
class ActStub:
    legislation_uri: str
    legislation_type: str
    title: str
    year: Optional[int] = None
    number: Optional[int] = None
    published_date: Optional[str] = None
    updated_date: Optional[str] = None
    html_url: Optional[str] = None
    xml_url: Optional[str] = None
    pdf_url: Optional[str] = None


def parse_feed(xml_bytes: bytes, leg_type: str) -> tuple[list[ActStub], bool]:
    """Parse one Atom feed page. Returns (stubs, has_next_page)."""
    root = etree.fromstring(xml_bytes)
    stubs: list[ActStub] = []

    for entry in root.findall("atom:entry", NS):
        id_el = entry.find("atom:id", NS)
        if id_el is None or not id_el.text:
            continue
        # id looks like http://www.legislation.gov.uk/id/ukpga/2021/1
        m = re.search(r"/id/(.+)$", id_el.text.strip())
        if not m:
            continue
        uri = m.group(1).strip("/")

        title_el = entry.find("atom:title", NS)
        title = title_el.text.strip() if title_el is not None and title_el.text else uri

        stub = ActStub(
            legislation_uri=uri,
            legislation_type=leg_type,
            title=title,
            html_url=f"{BASE_URL}/{uri}",
            xml_url=f"{BASE_URL}/{uri}/data.xml",
        )

        year_el = entry.find("ukm:Year", NS)
        if year_el is not None and (year_el.get("Value") or "").isdigit():
            stub.year = int(year_el.get("Value"))
        else:
            # Fall back to a 4-digit segment in the URI (regnal-year URIs have none)
            for part in uri.split("/"):
                if re.fullmatch(r"\d{4}", part):
                    stub.year = int(part)
                    break

        num_el = entry.find("ukm:Number", NS)
        if num_el is not None and (num_el.get("Value") or "").isdigit():
            stub.number = int(num_el.get("Value"))
        else:
            last = uri.rsplit("/", 1)[-1]
            if last.isdigit():
                stub.number = int(last)

        pub_el = entry.find("atom:published", NS)
        if pub_el is not None and pub_el.text:
            stub.published_date = pub_el.text.strip()[:10]
        upd_el = entry.find("atom:updated", NS)
        if upd_el is not None and upd_el.text:
            stub.updated_date = upd_el.text.strip()[:10]

        for link in entry.findall("atom:link", NS):
            if (link.get("type") or "") == "application/pdf" and link.get("href"):
                stub.pdf_url = link.get("href")
                break

        stubs.append(stub)

    has_next = any(
        link.get("rel") == "next"
        for link in root.findall("atom:link", NS)
    )
    return stubs, has_next


# ─── CLML parsing (Phase B) ───────────────────────────────────────────────────

def _clml_text(el) -> str:
    """Extract plain text from a CLML element, formatting provision numbers
    and skipping amendment-annotation subtrees."""
    out: list[str] = []

    def walk(node) -> None:
        ln = _local(node.tag)
        if ln in SKIP_SUBTREES:
            return
        if ln == "Pnumber":
            num = "".join(node.itertext()).strip()
            parent = node.getparent()
            parent_ln = _local(parent.tag) if parent is not None else ""
            out.append(f"{num}." if parent_ln == "P1" else f"({num})")
            return
        if node.text and node.text.strip():
            out.append(node.text.strip())
        for child in node:
            walk(child)
            if child.tail and child.tail.strip():
                out.append(child.tail.strip())
        if ln in {"Text", "Title", "P1", "P2", "P3", "Para", "LongTitle"}:
            out.append("\n")

    walk(el)
    text = " ".join(out)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_repealed_text(text: str) -> bool:
    """Repealed/omitted provisions render as ellipsis placeholders in revised CLML."""
    return bool(re.fullmatch(r"[.\s…·]*", text or ""))


def _child_text(el, localname: str) -> Optional[str]:
    for child in el:
        if _local(child.tag) == localname:
            t = "".join(child.itertext()).strip()
            return t or None
    return None


def _find_first(root, localname: str):
    for el in root.iter():
        if _local(el.tag) == localname:
            return el
    return None


def _parse_extent(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    mapping = {"E": "E", "W": "W", "S": "S", "N.I.": "NI", "NI": "NI"}
    out = []
    for token in raw.split("+"):
        v = mapping.get(token.strip())
        if v and v not in out:
            out.append(v)
    return out


def parse_clml(xml_bytes: bytes, stub: ActStub) -> dict:
    """Parse a CLML document into the Act JSON schema (ACTS_README.md §4)."""
    root = etree.fromstring(xml_bytes)
    if _local(root.tag) != "Legislation":
        raise ValueError(f"Unexpected root element <{_local(root.tag)}> — not CLML")

    # ── Metadata ──
    title = stub.title
    dc_title = root.find(".//dc:title", NS)
    if dc_title is not None and dc_title.text:
        title = dc_title.text.strip()

    long_title = None
    lt_el = _find_first(root, "LongTitle")
    if lt_el is not None:
        long_title = _clml_text(lt_el) or None

    enactment_date = None
    en_el = root.find(".//ukm:EnactmentDate", NS)
    if en_el is not None:
        enactment_date = en_el.get("Date")

    year = stub.year
    number = stub.number
    y_el = root.find(".//ukm:Year", NS)
    if y_el is not None and (y_el.get("Value") or "").isdigit():
        year = int(y_el.get("Value"))
    n_el = root.find(".//ukm:Number", NS)
    if n_el is not None and (n_el.get("Value") or "").isdigit():
        number = int(n_el.get("Value"))

    pdf_url = stub.pdf_url
    if not pdf_url:
        for alt in root.findall(".//ukm:Alternatives/ukm:Alternative", NS):
            uri = alt.get("URI") or ""
            if uri.lower().endswith(".pdf"):
                pdf_url = uri
                break

    extent = _parse_extent(root.get("RestrictExtent"))
    has_unapplied = root.find(".//ukm:UnappliedEffects/*", NS) is not None

    status = "unknown"
    if "(repealed" in title.lower():
        status = "repealed"

    # ── Body: sections grouped under Parts/Chapters ──
    sections: list[dict] = []
    contents: list[dict] = []
    unstructured_body_text = ""
    body = _find_first(root, "Body")
    current_part: Optional[str] = None
    position = 0

    if body is not None:
        for el in body.iter():
            ln = _local(el.tag)
            if ln in ("Part", "Chapter"):
                num = _child_text(el, "Number")
                head = _child_text(el, "Title")
                current_part = " — ".join(x for x in (num, head) if x) or current_part
                if num or head:
                    contents.append({
                        "level": ln.lower(),
                        "number": num,
                        "heading": head,
                    })
            elif ln == "P1group":
                heading = _child_text(el, "Title")
                sec_number = None
                text_parts: list[str] = []
                for child in el:
                    cln = _local(child.tag)
                    if cln == "Title":
                        continue
                    if cln == "P1" and sec_number is None:
                        pn = _child_text(child, "Pnumber")
                        sec_number = pn
                    if cln in ("P1", "P"):
                        text_parts.append(_clml_text(child))
                text = "\n".join(p for p in text_parts if p).strip()
                if sec_number is None and not text:
                    continue
                position += 1
                sec_id = f"section-{sec_number or position}".lower().replace(" ", "")
                repealed = _is_repealed_text(re.sub(r"^\s*\S+\.\s*", "", text, count=1))
                sections.append({
                    "id": sec_id,
                    "number": sec_number,
                    "heading": heading,
                    "part": current_part,
                    "repealed": repealed,
                    "text": text,
                })
                contents.append({
                    "level": "section",
                    "number": sec_number,
                    "heading": heading,
                    "parent": current_part,
                })

        # Older / unstructured CLML may have body text without P1group sections
        if not sections:
            unstructured_body_text = _clml_text(body)

    # ── Schedules ──
    schedules: list[dict] = []
    schedules_el = _find_first(root, "Schedules")
    if schedules_el is not None:
        for el in schedules_el:
            if _local(el.tag) != "Schedule":
                continue
            num = _child_text(el, "Number")
            tb = _find_first(el, "TitleBlock")
            head = _child_text(tb, "Title") if tb is not None else None
            text = _clml_text(el)
            position += 1
            sched_id = f"schedule-{(num or str(position)).lower()}"
            sched_id = re.sub(r"[^a-z0-9-]+", "-", sched_id).strip("-")
            schedules.append({
                "id": sched_id,
                "number": num,
                "heading": head,
                "text": text,
            })
            contents.append({"level": "schedule", "number": num, "heading": head})

    # ── Full text ──
    pieces: list[str] = [title]
    if long_title:
        pieces.append(long_title)
    if unstructured_body_text:
        pieces.append(unstructured_body_text)
    for s in sections:
        header = " ".join(x for x in (s["number"], s["heading"]) if x)
        pieces.append(f"{header}\n{s['text']}".strip())
    for s in schedules:
        header = " ".join(x for x in (s["number"], s["heading"]) if x)
        pieces.append(f"{header}\n{s['text']}".strip())
    full_text = "\n\n".join(p for p in pieces if p)

    full_text_truncated = False
    if len(full_text.encode()) > MAX_FULL_TEXT_BYTES:
        full_text = full_text.encode()[:MAX_FULL_TEXT_BYTES].decode(errors="ignore")
        full_text_truncated = True

    record = {
        "legislation_uri": stub.legislation_uri,
        "legislation_type": stub.legislation_type,
        "year": year,
        "number": number,
        "title": title,
        "long_title": long_title,
        "version_captured": "current",
        "version_date": None,
        "enactment_date": enactment_date,
        "extent": extent,
        "status": status,
        "has_unapplied_effects": has_unapplied,
        "format": "xml",
        "contents": contents,
        "sections": sections,
        "schedules": schedules,
        "full_text": full_text,
        "html_url": stub.html_url,
        "xml_url": stub.xml_url,
        "pdf_url": pdf_url,
        "fetched_at": _now(),
    }
    if full_text_truncated:
        record["full_text_truncated"] = True
    return record


def parse_resources_metadata(xml_bytes: bytes, stub: ActStub) -> dict:
    """Build a metadata-only record from /resources/data.xml (PDF-only Acts)."""
    title = stub.title
    long_title = None
    enactment_date = None
    pdf_url = stub.pdf_url
    extent: list[str] = []

    try:
        root = etree.fromstring(xml_bytes)
        dc_title = root.find(".//dc:title", NS)
        if dc_title is not None and dc_title.text:
            title = dc_title.text.strip()
        en_el = root.find(".//ukm:EnactmentDate", NS)
        if en_el is not None:
            enactment_date = en_el.get("Date")
        if not pdf_url:
            for alt in root.iter():
                if _local(alt.tag) == "Alternative":
                    uri = alt.get("URI") or ""
                    if uri.lower().endswith(".pdf"):
                        pdf_url = uri
                        break
        extent = _parse_extent(root.get("RestrictExtent"))
    except etree.XMLSyntaxError:
        pass

    return {
        "legislation_uri": stub.legislation_uri,
        "legislation_type": stub.legislation_type,
        "year": stub.year,
        "number": stub.number,
        "title": title,
        "long_title": long_title,
        "version_captured": "enacted",
        "version_date": None,
        "enactment_date": enactment_date,
        "extent": extent,
        "status": "unknown",
        "has_unapplied_effects": False,
        "format": "pdf_only",
        "contents": [],
        "sections": [],
        "schedules": [],
        "full_text": "",
        "html_url": stub.html_url,
        "xml_url": None,
        "pdf_url": pdf_url,
        "fetched_at": _now(),
    }


# ─── Paths ────────────────────────────────────────────────────────────────────

def _act_path(uri: str) -> Path:
    """Map e.g. 'ukpga/2021/1' → data/acts/ukpga/2021/1.json"""
    parts = uri.split("/")
    *dirs, filename = parts
    return ACTS_DIR.joinpath(*dirs) / f"{filename}.json"


def _pdf_path(uri: str) -> Path:
    parts = uri.split("/")
    *dirs, filename = parts
    return ACTS_PDF_DIR.joinpath(*dirs) / f"{filename}.pdf"


def _load_index(types: list[str]) -> list[ActStub]:
    stubs: list[ActStub] = []
    seen: set[str] = set()
    if not ACTS_INDEX_DIR.exists():
        return stubs
    for leg_type in types:
        for f in sorted(ACTS_INDEX_DIR.glob(f"{leg_type}_page_*.json")):
            try:
                data = json.loads(f.read_text())
            except Exception:
                continue
            for s in data:
                valid = {k: v for k, v in s.items() if k in ActStub.__dataclass_fields__}
                stub = ActStub(**valid)
                if stub.legislation_uri not in seen:
                    seen.add(stub.legislation_uri)
                    stubs.append(stub)
    return stubs


# ─── Terminal UI ──────────────────────────────────────────────────────────────

console = Console()

TYPE_COLOURS = {
    "UKPGA": "bold yellow",
    "ASP": "bold cyan",
    "ASC": "bold blue",
    "ANAW": "blue",
    "NIA": "magenta",
    "UKLA": "green",
}


class UI:
    def __init__(self, cursor: Cursor):
        self.cursor = cursor
        self.log: deque[Text] = deque(maxlen=12)
        self._start_time = time.monotonic()
        self._rate_window: deque[float] = deque(maxlen=60)

        self.progress = Progress(
            SpinnerColumn(style="bold cyan"),
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=40, style="cyan", complete_style="bold cyan"),
            MofNCompleteColumn(),
            TextColumn("[cyan]{task.percentage:>5.1f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
            expand=True,
        )
        self.task_id: Optional[TaskID] = None

    def _header(self) -> Panel:
        title = Text()
        title.append("§  ", style="bold yellow")
        title.append("LAWYERS DECK", style="bold white")
        title.append("  —  legislation.gov.uk UK Acts Worker", style="dim white")
        return Panel(title, style="bold cyan", padding=(0, 2))

    def _stats_panel(self) -> Panel:
        t = Table.grid(padding=(0, 2))
        t.add_column(justify="right", style="dim")
        t.add_column()

        phase_style = "bold cyan" if self.cursor.phase == "indexing" else "bold green"
        t.add_row("Phase", Text(self.cursor.phase.upper(), style=phase_style))
        t.add_row("Types", ", ".join(self.cursor.types))

        if self.cursor.phase == "indexing":
            current = (
                self.cursor.types[self.cursor.type_index]
                if self.cursor.type_index < len(self.cursor.types)
                else "—"
            )
            t.add_row("Indexing type", f"[cyan]{current}[/] (page {self.cursor.index_page})")
            t.add_row("Acts found", f"[green]{self.cursor.total_acts:,}")
        else:
            t.add_row(
                "Fetched",
                f"[green]{self.cursor.fetched:,}[/] / [white]{self.cursor.total_acts:,}",
            )
            t.add_row("PDF-only", f"[yellow]{self.cursor.pdf_only:,}")
            t.add_row("Errors", f"[red]{self.cursor.errors:,}")
            t.add_row("Skipped (cached)", f"[dim]{self.cursor.skipped:,}")

        elapsed = time.monotonic() - self._start_time
        h, m, s = int(elapsed // 3600), int((elapsed % 3600) // 60), int(elapsed % 60)
        t.add_row("Elapsed", f"{h:02d}:{m:02d}:{s:02d}")

        if self._rate_window:
            rate = len(self._rate_window) / max(
                self._rate_window[-1] - self._rate_window[0] + 0.001, 0.001
            )
            t.add_row("Speed", f"[cyan]{rate:.1f}[/] / sec")

        return Panel(t, title="[bold]Statistics", border_style="cyan", padding=(0, 1))

    def _log_panel(self) -> Panel:
        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column(width=2)
        t.add_column()
        if not self.log:
            t.add_row("", Text("Waiting…", style="dim"))
        for line in self.log:
            t.add_row("", line)
        return Panel(t, title="[bold]Recent activity", border_style="cyan", padding=(0, 1))

    def build(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(self._header(), name="header", size=3),
            Layout(name="body"),
            Layout(Panel(self.progress, border_style="cyan", padding=(0, 1)), name="progress", size=5),
        )
        layout["body"].split_row(
            Layout(self._stats_panel(), name="stats", ratio=1),
            Layout(self._log_panel(), name="log", ratio=2),
        )
        return layout

    def tick(self, stub: Optional[ActStub] = None, ok: bool = True, msg: str = "") -> None:
        self._rate_window.append(time.monotonic())
        if stub:
            icon = Text("✓ " if ok else "✗ ", style="green" if ok else "red")
            type_tag = Text(
                stub.legislation_type.upper(),
                style=TYPE_COLOURS.get(stub.legislation_type.upper(), "white"),
            )
            uri = Text(f" {stub.legislation_uri} ", style="bold white")
            name = Text(stub.title[:55], style="white" if ok else "red dim")
            suffix = Text(f"  {msg}", style="yellow") if msg else Text("")
            self.log.append(Text.assemble(icon, type_tag, uri, name, suffix))
        elif msg:
            self.log.append(Text(msg, style="dim"))

    def add_progress_task(self, description: str, total: int) -> TaskID:
        self.task_id = self.progress.add_task(description, total=total)
        return self.task_id

    def advance(self, n: int = 1) -> None:
        if self.task_id is not None:
            self.progress.advance(self.task_id, n)

    def update_task(self, description: str, total: int, completed: int) -> None:
        if self.task_id is not None:
            self.progress.update(
                self.task_id, description=description, total=total, completed=completed
            )


# ─── Worker phases ────────────────────────────────────────────────────────────

async def phase_index(
    cursor: Cursor,
    ui: UI,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    delay: float,
    live: Live,
) -> None:
    """Phase A — page through each type's Atom feed and build the stub index."""
    ACTS_INDEX_DIR.mkdir(parents=True, exist_ok=True)

    # Count already-indexed acts
    existing_uris: set[str] = set()
    for f in ACTS_INDEX_DIR.glob("*_page_*.json"):
        try:
            for s in json.loads(f.read_text()):
                existing_uris.add(s.get("legislation_uri", ""))
        except Exception:
            pass
    cursor.total_acts = len(existing_uris)

    ui.add_progress_task("Indexing Atom feeds", total=len(cursor.types))
    ui.progress.update(ui.task_id, completed=cursor.type_index)  # type: ignore[arg-type]

    while cursor.type_index < len(cursor.types):
        leg_type = cursor.types[cursor.type_index]
        page = cursor.index_page

        while True:
            index_file = ACTS_INDEX_DIR / f"{leg_type}_page_{page:05d}.json"

            if index_file.exists():
                # Already saved on a previous run — trust it and continue
                data = json.loads(index_file.read_text())
                has_next = bool(data) and len(data) >= RESULTS_PER_PAGE
            else:
                url = f"{BASE_URL}/{leg_type}/data.feed?results-count={RESULTS_PER_PAGE}&page={page}"
                resp = await get(client, url, sem, delay)
                if resp is None:
                    ui.tick(msg=f"[red]Failed to fetch feed {leg_type} page {page}")
                    cursor.errors += 1
                    break
                try:
                    stubs, has_next = parse_feed(resp.content, leg_type)
                except etree.XMLSyntaxError as e:
                    ui.tick(msg=f"[red]Bad feed XML {leg_type} p{page}: {str(e)[:40]}")
                    cursor.errors += 1
                    break
                new = [s for s in stubs if s.legislation_uri not in existing_uris]
                for s in new:
                    existing_uris.add(s.legislation_uri)
                index_file.write_text(
                    json.dumps([asdict(s) for s in stubs], indent=2, ensure_ascii=False)
                )
                cursor.total_acts = len(existing_uris)
                ui.tick(msg=f"{leg_type} page {page}: {len(stubs)} acts ({cursor.total_acts:,} total)")

            page += 1
            cursor.index_page = page
            cursor.save(CURSOR_FILE)
            live.update(ui.build())

            if not has_next:
                break

        cursor.type_index += 1
        cursor.index_page = 1
        cursor.save(CURSOR_FILE)
        ui.advance()
        live.update(ui.build())

    cursor.phase = "fetching"
    cursor.save(CURSOR_FILE)
    ui.tick(msg=f"[green]Indexing complete — {cursor.total_acts:,} acts found")
    live.update(ui.build())


async def fetch_one(
    stub: ActStub,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    delay: float,
    skip_pdfs: bool,
) -> tuple[str, dict | None, str]:
    """Fetch one Act. Returns (result, record, note) where result is
    'xml' | 'pdf_only' | 'error'."""
    xml_url = f"{BASE_URL}/{stub.legislation_uri}/data.xml"
    resp = await get(client, xml_url, sem, delay)

    record: dict | None = None
    if resp is not None and b"<" in resp.content[:100]:
        try:
            record = parse_clml(resp.content, stub)
        except (etree.XMLSyntaxError, ValueError) as e:
            return "error", None, f"CLML parse failed: {str(e)[:60]}"

        # A CLML metadata shell with no body text means the real content only
        # exists as a scanned PDF — fall through to the PDF path.
        has_text = bool(record["sections"] or record["schedules"]) or (
            len(record["full_text"]) > len(record["title"]) + len(record["long_title"] or "") + 50
        )
        if has_text:
            return "xml", record, ""
        record["format"] = "pdf_only"

    if record is None:
        # No XML at all — build a metadata-only record from /resources.
        meta_url = f"{BASE_URL}/{stub.legislation_uri}/resources/data.xml"
        meta_resp = await get(client, meta_url, sem, delay)
        record = parse_resources_metadata(
            meta_resp.content if meta_resp is not None else b"", stub
        )

    note = "no text in XML — metadata only"
    if record["pdf_url"] and not skip_pdfs:
        pdf_resp = await get(client, record["pdf_url"], sem, delay)
        if pdf_resp is not None and pdf_resp.content[:4] == b"%PDF":
            pdf_file = _pdf_path(stub.legislation_uri)
            pdf_file.parent.mkdir(parents=True, exist_ok=True)
            pdf_file.write_bytes(pdf_resp.content)
            record["pdf_path"] = str(pdf_file.relative_to(ROOT))
            note = "PDF saved"
        else:
            note = "PDF download failed"
    elif record["pdf_url"]:
        note = "PDF skipped (--skip-pdfs)"
    else:
        note = "no XML text and no PDF found"

    return "pdf_only", record, note


async def phase_fetch(
    cursor: Cursor,
    ui: UI,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    delay: float,
    live: Live,
    concurrency: int,
    skip_pdfs: bool,
    limit: Optional[int],
    only_uris: Optional[list[str]],
) -> None:
    """Phase B — fetch every Act and save as JSON (PDF fallback when no XML)."""
    stubs = _load_index(cursor.types)

    if only_uris:
        by_uri = {s.legislation_uri: s for s in stubs}
        stubs = []
        for uri in only_uris:
            leg_type = uri.split("/")[0]
            stubs.append(by_uri.get(uri) or ActStub(
                legislation_uri=uri,
                legislation_type=leg_type,
                title=uri,
                html_url=f"{BASE_URL}/{uri}",
                xml_url=f"{BASE_URL}/{uri}/data.xml",
            ))
    elif not stubs:
        ui.tick(msg="[red]No index found — run without --pages-only first")
        return

    cursor.total_acts = max(cursor.total_acts, len(stubs))

    ui.update_task("Fetching acts", total=len(stubs), completed=0)
    live.update(ui.build())

    queue: asyncio.Queue[ActStub] = asyncio.Queue()
    for stub in stubs:
        await queue.put(stub)

    processed = 0
    fetched_this_run = 0
    lock = asyncio.Lock()
    stop = asyncio.Event()

    async def worker() -> None:
        nonlocal processed, fetched_this_run
        while not stop.is_set():
            try:
                stub = queue.get_nowait()
            except asyncio.QueueEmpty:
                return

            path = _act_path(stub.legislation_uri)

            if path.exists() and not only_uris:
                async with lock:
                    cursor.skipped += 1
                    processed += 1
                    ui.advance()
                    if processed % 50 == 0:
                        cursor.save(CURSOR_FILE)
                    live.update(ui.build())
                queue.task_done()
                continue

            result, record, note = await fetch_one(stub, client, sem, delay, skip_pdfs)

            async with lock:
                if record is not None:
                    try:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
                        cursor.fetched += 1
                        fetched_this_run += 1
                        if result == "pdf_only":
                            cursor.pdf_only += 1
                        ui.tick(stub=stub, ok=True, msg=note)
                    except Exception as e:
                        cursor.errors += 1
                        ui.tick(stub=stub, ok=False, msg=str(e)[:60])
                else:
                    cursor.errors += 1
                    ui.tick(stub=stub, ok=False, msg=note)

                processed += 1
                ui.advance()
                if processed % 25 == 0:
                    cursor.save(CURSOR_FILE)
                live.update(ui.build())

                if limit is not None and fetched_this_run >= limit:
                    stop.set()

            queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
    await asyncio.gather(*workers)

    if not only_uris and limit is None:
        cursor.phase = "done"
    cursor.save(CURSOR_FILE)

    ui.tick(
        msg=f"[bold green]Done — {cursor.fetched:,} acts saved "
        f"({cursor.pdf_only:,} PDF-only), {cursor.errors:,} errors"
    )
    live.update(ui.build())


# ─── Entry point ─────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> None:
    ACTS_DIR.mkdir(parents=True, exist_ok=True)

    types = [t.strip() for t in args.types.split(",") if t.strip()]
    unknown = [t for t in types if t not in KNOWN_TYPES]
    if unknown:
        console.print(f"[red]Unknown legislation type(s): {', '.join(unknown)}")
        console.print(f"[dim]Known types: {', '.join(KNOWN_TYPES)}")
        sys.exit(1)

    cursor = Cursor.load(CURSOR_FILE)

    if args.reset:
        cursor.reset(types)
        cursor.save(CURSOR_FILE)
        if ACTS_INDEX_DIR.exists():
            for f in ACTS_INDEX_DIR.glob("*.json"):
                f.unlink()
        console.print("[yellow]Cursor reset. Starting from scratch.[/]")
    elif types != cursor.types:
        # Types changed between runs — re-run indexing for the new set
        cursor.types = types
        cursor.type_index = 0
        cursor.index_page = 1
        cursor.phase = "indexing"

    only_uris = [u.strip().strip("/") for u in args.uri] if args.uri else None

    if cursor.phase == "done" and not args.reset and not only_uris:
        console.print(
            f"[green]All done![/] {cursor.fetched:,} acts already fetched. "
            "Use [bold]--reset[/] to start over, or [bold]--uri[/] to refresh specific acts."
        )
        return

    sem = asyncio.Semaphore(args.concurrency)
    ui = UI(cursor)

    limits = httpx.Limits(
        max_connections=args.concurrency + 2,
        max_keepalive_connections=args.concurrency,
    )
    async with httpx.AsyncClient(limits=limits, follow_redirects=True) as client:
        with Live(ui.build(), console=console, refresh_per_second=4, screen=False) as live:
            if cursor.phase == "indexing" and not only_uris:
                await phase_index(cursor, ui, client, sem, args.delay, live)

            if only_uris and ui.task_id is None:
                ui.add_progress_task("Fetching acts", total=len(only_uris))

            if (cursor.phase == "fetching" or only_uris) and not args.pages_only:
                await phase_fetch(
                    cursor, ui, client, sem, args.delay, live,
                    args.concurrency, args.skip_pdfs, args.limit, only_uris,
                )
            elif args.pages_only and cursor.phase == "fetching":
                ui.tick(msg="[cyan]--pages-only flag set. Stopping after index.")
                live.update(ui.build())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lawyers Deck — legislation.gov.uk UK Acts ingestion worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Clear cursor and index, start from scratch",
    )
    parser.add_argument(
        "--types", type=str, default=",".join(DEFAULT_TYPES), metavar="T1,T2",
        help=f"Comma-separated legislation types (default: {','.join(DEFAULT_TYPES)}; "
             f"known: {','.join(KNOWN_TYPES)})",
    )
    parser.add_argument(
        "--concurrency", type=int, default=3, metavar="N",
        help="Number of parallel requests (default: 3 — stay well under fair-use limits)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.5, metavar="SECS",
        help="Seconds between requests per worker (default: 0.5)",
    )
    parser.add_argument(
        "--pages-only", action="store_true",
        help="Only build the Atom feed index; skip fetching act content",
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Stop after N successful fetches this run (for pilots)",
    )
    parser.add_argument(
        "--uri", action="append", default=None, metavar="URI",
        help="Fetch only the given legislation URI(s), e.g. --uri ukpga/2021/1 "
             "(repeatable; re-fetches even if the file exists)",
    )
    parser.add_argument(
        "--skip-pdfs", action="store_true",
        help="Do not download PDFs for acts that have no XML",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Progress saved to acts_cursor.txt — run again to resume.[/]")
        sys.exit(0)


if __name__ == "__main__":
    main()
