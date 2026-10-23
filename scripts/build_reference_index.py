"""Index every prior research report so the Director and Critic see what was already measured.

Scans reference/gj-strat (results/**/*.md, green/*.md, docs) and reference/trade-research/docs, and writes
runs/reference_index.md: one entry per report with its title and opening summary, plus the grep
command to read the full file. Re-run after adding reference material.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs" / "reference_index.md"
SOURCES = [
    ROOT / "reference" / "gj-strat" / "results",
    ROOT / "reference" / "gj-strat" / "green",
    ROOT / "reference" / "trade-research" / "docs",
]
MAX_SUMMARY = 420


def summarize(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln.rstrip() for ln in text.splitlines()]
    title = next((ln.lstrip("# ").strip() for ln in lines if ln.startswith("#")), path.stem)
    body: list[str] = []
    started = False
    for ln in lines:
        if ln.startswith("#"):
            if started:
                break
            started = True
            continue
        if not started:
            continue
        s = ln.strip()
        if not s or s.startswith("|--"):
            if body:
                break
            continue
        body.append(re.sub(r"\s+", " ", s))
        if sum(len(b) for b in body) > MAX_SUMMARY:
            break
    summary = " ".join(body)[:MAX_SUMMARY]
    return title, summary


def main() -> None:
    entries = []
    for src in SOURCES:
        if not src.exists():
            continue
        for path in sorted(src.rglob("*.md")):
            rel = path.relative_to(ROOT).as_posix()
            title, summary = summarize(path)
            entries.append((rel, title, summary))
    lines = ["# Prior research reports (already measured; do not re-test without a different mechanism)", "",
             f"{len(entries)} reports. Read any of them with the Read tool, or grep `reference/gj-strat/results` for a keyword, "
             "before proposing. Each line: path | title | opening summary.", ""]
    for rel, title, summary in entries:
        lines.append(f"- `{rel}` | {title} | {summary}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(entries)} reports -> {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    sys.exit(main())
