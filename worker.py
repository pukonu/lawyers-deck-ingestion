#!/usr/bin/env python3
"""
Lawyers Deck — National Archives Find Case Law Ingestion Worker
==============================================================
Pulls every judgment from caselaw.nationalarchives.gov.uk and saves
each one as a JSON file, resuming from where it left off via cursor.txt.

Usage
-----
  python worker.py                  # run / resume
  python worker.py --reset          # start over from page 1
  python worker.py --concurrency 8  # parallel requests (default: 5)
  python worker.py --delay 0.5      # seconds between requests (default: 0.3)
  python worker.py --pages-only     # only build the index, skip full fetch
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from rich.columns import Columns
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
JUDGMENTS_DIR = DATA_DIR / "judgments"
INDEX_DIR = DATA_DIR / "index"
CURSOR_FILE = ROOT / "cursor.txt"

# ─── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://caselaw.nationalarchives.gov.uk"
TOTAL_PAGES = 7646
SEARCH_URL = BASE_URL + "/search?order=-date&page={page}"
HEADERS = {
    "User-Agent": "LawyersDeckIngestion/1.0 (+https://lawyersdeck.com; research)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9",
}
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30.0
MAX_FULL_TEXT_BYTES = 500_000  # ~500 KB cap per judgment

MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

# ─── State / Cursor ───────────────────────────────────────────────────────────

@dataclass
class Cursor:
    phase: str = "indexing"        # "indexing" | "fetching" | "done"
    index_page: int = 1            # next search page to index
    fetch_offset: int = 0          # next URI index to fetch
    total_pages: int = TOTAL_PAGES
    total_judgments: int = 0       # known after indexing completes
    fetched: int = 0               # successfully saved
    errors: int = 0                # failed fetches
    skipped: int = 0               # already on disk
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

    def reset(self) -> None:
        self.phase = "indexing"
        self.index_page = 1
        self.fetch_offset = 0
        self.total_judgments = 0
        self.fetched = 0
        self.errors = 0
        self.skipped = 0
        self.started_at = _now()
        self.updated_at = _now()


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

async def get_html(
    client: httpx.AsyncClient,
    url: str,
    sem: asyncio.Semaphore,
    delay: float,
    retries: int = MAX_RETRIES,
) -> Optional[str]:
    async with sem:
        for attempt in range(retries):
            try:
                await asyncio.sleep(delay)
                r = await client.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                if r.status_code == 200:
                    return r.text
                if r.status_code == 404:
                    return None
                if r.status_code == 429:
                    await asyncio.sleep(10 * (attempt + 1))
                elif r.status_code >= 500:
                    await asyncio.sleep(3 * (attempt + 1))
                else:
                    return None
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError):
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
        return None


# ─── Parsing ──────────────────────────────────────────────────────────────────

@dataclass
class JudgmentStub:
    tna_uri: str
    case_name: str
    neutral_citation: Optional[str] = None
    court: Optional[str] = None
    division: Optional[str] = None
    date_handed_down: Optional[str] = None
    html_url: Optional[str] = None


def parse_search_page(html: str) -> list[JudgmentStub]:
    """
    Parse the search results table. Each result spans two <tbody> groups:
      tbody 1, tr 1: <td colspan=3> contains the <a href="/court/year/num">Case Name</a>
      tbody 1, tr 2: court name | neutral citation | date
    """
    soup = BeautifulSoup(html, "lxml")
    results: list[JudgmentStub] = []

    # The results live inside <div class="documents-table"><table>
    table = soup.find("div", class_="documents-table")
    if not table:
        table = soup  # fallback: search the whole page

    for tbody in table.find_all("tbody"):
        rows = tbody.find_all("tr", recursive=False)
        if not rows:
            continue

        # Row 0: link row
        link_td = rows[0].find("td")
        if not link_td:
            continue
        anchor = link_td.find("a", href=True)
        if not anchor:
            continue

        href = anchor["href"].strip()
        # Only accept URIs like /court/year/num or /court/division/year/num
        if not re.match(r"^/[a-z][a-z/-]*/\d{4}/\d+$", href):
            continue

        tna_uri = href.lstrip("/")
        case_name = anchor.get_text(strip=True)
        stub = JudgmentStub(
            tna_uri=tna_uri,
            case_name=case_name,
            html_url=BASE_URL + href,
        )

        # Infer court / division from URI
        parts = tna_uri.split("/")
        if len(parts) == 3:
            stub.court = parts[0].upper().replace("-", "")
        elif len(parts) == 4:
            stub.court = parts[0].upper().replace("-", "")
            stub.division = parts[1].upper()

        # Row 1: metadata row (court label | citation | date)
        if len(rows) > 1:
            cells = rows[1].find_all("td")
            for cell in cells:
                text = cell.get_text(strip=True)
                # Citation: "[2026] EWHC 1172 (Admin)" or "[2026] UKSC 15"
                m = re.search(r"\[\d{4}\]\s+[A-Z]+\s+\d+(?:\s+\([A-Za-z]+\))?", text)
                if m:
                    stub.neutral_citation = m.group(0).strip()
                    continue
                # Date: "15 May 2026" or "Handed down15 May 2026"
                d = _parse_date(text)
                if d:
                    stub.date_handed_down = d

        results.append(stub)

    return results


def parse_judgment(html: str, stub: JudgmentStub) -> dict:
    """Extract full text, judges, and metadata from an individual judgment page."""
    soup = BeautifulSoup(html, "lxml")

    # ── Case name ──
    case_name = stub.case_name
    h1 = soup.find("h1")
    if h1:
        candidate = h1.get_text(strip=True)
        if len(candidate) > 5:
            case_name = candidate

    # ── Neutral citation ──
    neutral_citation = stub.neutral_citation
    for text_node in soup.find_all(string=re.compile(r"\[\d{4}\]")):
        m = re.search(r"\[\d{4}\]\s+[A-Z]{2,8}(?:\s+[A-Z][A-Za-z]+)?\s+\d+", text_node)
        if m:
            neutral_citation = m.group(0).strip()
            break

    # ── Date ──
    date = stub.date_handed_down
    time_el = soup.find("time")
    if time_el:
        date = _parse_date(time_el.get("datetime") or time_el.get_text(strip=True)) or date

    # ── Judges ──
    judge_re = re.compile(
        r"\b(?:HH?J|Lord|Lady|Baroness|Sir|"
        r"(?:Mr|Mrs|Ms|Miss|Master)\s+Justice|"
        r"Lord Justice|Lady Justice)\s+[A-Z][A-Za-z\-]+(?:\s+[A-Z][A-Za-z\-]+)*"
    )
    judges_seen: dict[str, None] = {}
    body = soup.find(class_="judgment-body") or soup.find("main") or soup
    for text_node in body.find_all(string=judge_re):
        for match in judge_re.finditer(str(text_node)):
            name = match.group(0).strip()
            if len(name) < 50:
                judges_seen[name] = None
    judges = list(judges_seen.keys())[:15]

    # ── Summary — pull from judgment body only, not cookie banners ──
    summary = None
    judgment_body_el = soup.find(class_="judgment-body")
    paras = [
        p.get_text(strip=True)
        for p in (judgment_body_el or soup).find_all("p")
        if len(p.get_text(strip=True)) > 100
    ]
    if paras:
        summary = paras[0][:600]

    # ── Full text ──
    judgment_body = soup.find(class_="judgment-body")
    if judgment_body:
        for tag in judgment_body.find_all(["script", "style", "nav"]):
            tag.decompose()
        raw_text = judgment_body.get_text("\n", strip=True)
    else:
        for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        raw_text = soup.get_text("\n", strip=True)

    # Normalise whitespace
    full_text = re.sub(r"\n{3,}", "\n\n", raw_text).strip()
    if len(full_text.encode()) > MAX_FULL_TEXT_BYTES:
        full_text = full_text.encode()[:MAX_FULL_TEXT_BYTES].decode(errors="ignore")

    return {
        "tna_uri": stub.tna_uri,
        "case_name": case_name,
        "neutral_citation": neutral_citation,
        "court": stub.court,
        "division": stub.division,
        "date_handed_down": date,
        "judges": judges,
        "parties": {},
        "summary": summary,
        "full_text": full_text,
        "html_url": stub.html_url,
        "xml_url": (stub.html_url or "").rstrip("/") + "/data.xml",
        "fetched_at": _now(),
    }


def _parse_date(raw: str) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    # ISO already
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    # "15 May 2026" anywhere in the string (handles "Handed down15 May 2026" prefix)
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if m:
        month = MONTH_MAP.get(m.group(2).lower())
        if month:
            return f"{m.group(3)}-{month}-{m.group(1).zfill(2)}"
    return None


def _judgment_path(tna_uri: str) -> Path:
    """Map e.g. 'uksc/2023/29' → data/judgments/uksc/2023/29.json"""
    parts = tna_uri.split("/")
    *dirs, filename = parts
    return JUDGMENTS_DIR.joinpath(*dirs) / f"{filename}.json"


def _load_index() -> list[JudgmentStub]:
    """Load all stubs from the index files."""
    stubs: list[JudgmentStub] = []
    if not INDEX_DIR.exists():
        return stubs
    for f in sorted(INDEX_DIR.glob("page_*.json")):
        try:
            data = json.loads(f.read_text())
            stubs.extend(JudgmentStub(**s) for s in data)
        except Exception:
            pass
    return stubs


# ─── Terminal UI ──────────────────────────────────────────────────────────────

console = Console()

COURT_COLOURS = {
    "UKSC": "bold yellow",
    "EWCA": "bold cyan",
    "EWHC": "bold blue",
    "UKUT": "magenta",
    "UKFTT": "green",
    "UKEAT": "bright_red",
}


def _court_tag(court: Optional[str]) -> Text:
    c = (court or "—").upper()
    style = COURT_COLOURS.get(c, "white")
    return Text(c, style=style)


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
        title.append("⚖  ", style="bold yellow")
        title.append("LAWYERS DECK", style="bold white")
        title.append("  —  National Archives Ingestion Worker", style="dim white")
        return Panel(title, style="bold cyan", padding=(0, 2))

    def _stats_panel(self) -> Panel:
        t = Table.grid(padding=(0, 2))
        t.add_column(justify="right", style="dim")
        t.add_column()

        phase_style = "bold cyan" if self.cursor.phase == "indexing" else "bold green"
        t.add_row("Phase", Text(self.cursor.phase.upper(), style=phase_style))

        if self.cursor.phase == "indexing":
            done = self.cursor.index_page - 1
            total = self.cursor.total_pages
            t.add_row("Pages indexed", f"[cyan]{done:,}[/] / [white]{total:,}")
            pct = done / total * 100 if total else 0
            t.add_row("Judgment URIs found", f"[green]{self.cursor.total_judgments:,}")
        else:
            t.add_row(
                "Fetched",
                f"[green]{self.cursor.fetched:,}[/] / [white]{self.cursor.total_judgments:,}",
            )
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

            if self.cursor.phase == "fetching" and self.cursor.total_judgments:
                remaining = self.cursor.total_judgments - self.cursor.fetched - self.cursor.skipped
                if rate > 0 and remaining > 0:
                    eta_sec = remaining / rate
                    eh = int(eta_sec // 3600)
                    em = int((eta_sec % 3600) // 60)
                    t.add_row("ETA", f"[yellow]{eh}h {em}m")

        return Panel(t, title="[bold]Statistics", border_style="cyan", padding=(0, 1))

    def _log_panel(self) -> Panel:
        t = Table.grid(padding=(0, 1), expand=True)
        t.add_column(width=2)
        t.add_column(width=8)
        t.add_column()

        if not self.log:
            t.add_row("", "", Text("Waiting…", style="dim"))
        for line in self.log:
            t.add_row("", "", line)

        return Panel(t, title="[bold]Recent activity", border_style="cyan", padding=(0, 1))

    def _progress_panel(self) -> Panel:
        return Panel(self.progress, border_style="cyan", padding=(0, 1))

    def build(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(self._header(), name="header", size=3),
            Layout(name="body"),
            Layout(self._progress_panel(), name="progress", size=5),
        )
        layout["body"].split_row(
            Layout(self._stats_panel(), name="stats", ratio=1),
            Layout(self._log_panel(), name="log", ratio=2),
        )
        return layout

    def tick(self, stub: Optional[JudgmentStub] = None, ok: bool = True, msg: str = "") -> None:
        self._rate_window.append(time.monotonic())
        if stub:
            icon = Text("✓ " if ok else "✗ ", style="green" if ok else "red")
            court_tag = _court_tag(stub.court)
            cite = Text(f" {stub.neutral_citation or stub.tna_uri} ", style="bold white")
            name = Text(stub.case_name[:55], style="white" if ok else "red dim")
            line = Text.assemble(icon, court_tag, cite, name)
            self.log.append(line)
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
                self.task_id,
                description=description,
                total=total,
                completed=completed,
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
    """
    Phase 1 — crawl all search result pages and build a URI index.
    """
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    start_page = cursor.index_page
    total = cursor.total_pages

    ui.add_progress_task("Indexing search pages", total=total)
    ui.progress.update(ui.task_id, completed=start_page - 1)  # type: ignore[arg-type]

    ui.tick(msg=f"Resuming indexing from page {start_page:,} of {total:,}")
    live.update(ui.build())

    # Count already-found judgments from existing index files
    existing = sum(
        len(json.loads(f.read_text()))
        for f in INDEX_DIR.glob("page_*.json")
        if f.exists()
    )
    cursor.total_judgments = existing

    for page in range(start_page, total + 1):
        index_file = INDEX_DIR / f"page_{page:05d}.json"

        # Already indexed
        if index_file.exists():
            stubs = json.loads(index_file.read_text())
            cursor.index_page = page + 1
            cursor.total_judgments += 0  # already counted above
            ui.advance()
            live.update(ui.build())
            continue

        url = SEARCH_URL.format(page=page)
        html = await get_html(client, url, sem, delay)

        if html is None:
            ui.tick(msg=f"[red]Failed to fetch page {page}")
            cursor.errors += 1
        else:
            stubs = parse_search_page(html)
            index_file.write_text(json.dumps([asdict(s) for s in stubs], indent=2))
            cursor.total_judgments += len(stubs)
            ui.tick(msg=f"Page {page:,}: {len(stubs)} judgments")

        cursor.index_page = page + 1
        cursor.save(CURSOR_FILE)
        ui.advance()
        live.update(ui.build())

    cursor.phase = "fetching"
    cursor.save(CURSOR_FILE)
    ui.tick(msg=f"[green]Indexing complete — {cursor.total_judgments:,} judgments found")
    live.update(ui.build())


async def phase_fetch(
    cursor: Cursor,
    ui: UI,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    delay: float,
    live: Live,
    concurrency: int,
) -> None:
    """
    Phase 2 — fetch every judgment and save as JSON.
    """
    stubs = _load_index()

    if not stubs:
        ui.tick(msg="[red]No index found — run without --pages-only first")
        return

    cursor.total_judgments = len(stubs)
    start = cursor.fetch_offset
    remaining = stubs[start:]

    ui.update_task(
        "Fetching judgments",
        total=len(stubs),
        completed=start,
    )
    live.update(ui.build())

    queue: asyncio.Queue[JudgmentStub] = asyncio.Queue()
    for stub in remaining:
        await queue.put(stub)

    processed = 0
    lock = asyncio.Lock()

    async def worker() -> None:
        nonlocal processed
        while True:
            try:
                stub = queue.get_nowait()
            except asyncio.QueueEmpty:
                return

            path = _judgment_path(stub.tna_uri)

            # Skip if already saved
            if path.exists():
                async with lock:
                    cursor.skipped += 1
                    cursor.fetch_offset += 1
                    processed += 1
                    ui.advance()
                    if processed % 50 == 0:
                        cursor.save(CURSOR_FILE)
                    live.update(ui.build())
                queue.task_done()
                continue

            html = await get_html(client, stub.html_url or f"{BASE_URL}/{stub.tna_uri}", sem, delay)

            async with lock:
                if html:
                    try:
                        data = parse_judgment(html, stub)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
                        cursor.fetched += 1
                        ui.tick(stub=stub, ok=True)
                    except Exception as e:
                        cursor.errors += 1
                        ui.tick(stub=stub, ok=False, msg=str(e)[:60])
                else:
                    cursor.errors += 1
                    ui.tick(stub=stub, ok=False)

                cursor.fetch_offset += 1
                processed += 1
                ui.advance()

                if processed % 25 == 0:
                    cursor.save(CURSOR_FILE)
                live.update(ui.build())

            queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
    await asyncio.gather(*workers)

    cursor.fetch_offset = len(stubs)
    cursor.phase = "done"
    cursor.save(CURSOR_FILE)

    ui.tick(msg=f"[bold green]Done — {cursor.fetched:,} judgments saved, {cursor.errors:,} errors")
    live.update(ui.build())


# ─── Entry point ─────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JUDGMENTS_DIR.mkdir(parents=True, exist_ok=True)

    cursor = Cursor.load(CURSOR_FILE)

    if args.reset:
        cursor.reset()
        cursor.save(CURSOR_FILE)
        # Clear index
        if INDEX_DIR.exists():
            for f in INDEX_DIR.glob("*.json"):
                f.unlink()
        console.print("[yellow]Cursor reset. Starting from page 1.[/]")

    if cursor.phase == "done" and not args.reset:
        console.print(
            f"[green]All done![/] {cursor.fetched:,} judgments already fetched. "
            "Use [bold]--reset[/] to start over."
        )
        return

    sem = asyncio.Semaphore(args.concurrency)
    ui = UI(cursor)

    limits = httpx.Limits(max_connections=args.concurrency + 2, max_keepalive_connections=args.concurrency)
    async with httpx.AsyncClient(limits=limits, follow_redirects=True) as client:
        with Live(ui.build(), console=console, refresh_per_second=4, screen=False) as live:
            if cursor.phase == "indexing":
                await phase_index(cursor, ui, client, sem, args.delay, live)

            if cursor.phase == "fetching" and not args.pages_only:
                await phase_fetch(cursor, ui, client, sem, args.delay, live, args.concurrency)
            elif args.pages_only and cursor.phase == "fetching":
                ui.tick(msg="[cyan]--pages-only flag set. Stopping after index.")
                live.update(ui.build())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lawyers Deck — Find Case Law ingestion worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Clear cursor and start from page 1",
    )
    parser.add_argument(
        "--concurrency", type=int, default=5, metavar="N",
        help="Number of parallel requests (default: 5)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.3, metavar="SECS",
        help="Seconds between requests per worker (default: 0.3)",
    )
    parser.add_argument(
        "--pages-only", action="store_true",
        help="Only build the URI index; skip fetching full judgment text",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Progress saved to cursor.txt — run again to resume.[/]")
        sys.exit(0)


if __name__ == "__main__":
    main()
