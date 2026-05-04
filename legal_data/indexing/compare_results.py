#!/usr/bin/env python3
"""Print a side-by-side comparison of UK Legal vs Node.js evaluation summaries.

Reads:
- version-aware-RAG/data/results/evaluation_summary_nodejs.txt (Node.js baseline)
- version-aware-RAG/data/results/evaluation_summary_uk.txt     (UK Legal)

Before running this for the first time, snapshot the Node.js baseline:
    cp data/results/evaluation_summary.txt data/results/evaluation_summary_nodejs.txt

Usage:
    python3 OD/indexing/compare_results.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent.parent / "version-aware-RAG" / "data" / "results"
SUMMARY_NODEJS = RESULTS / "evaluation_summary_nodejs.txt"
SUMMARY_UK = RESULTS / "evaluation_summary_uk.txt"


def parse_summary(text: str) -> dict[str, tuple[int, int]]:
    """Parse 'Label  X/Y (Z%)' lines into a dict {label: (correct, total)}."""
    out: dict[str, tuple[int, int]] = {}
    for line in text.splitlines():
        m = re.match(r"^\s*(.+?)\s+(\d+)\s*/\s*(\d+)\s*\(\d", line)
        if m:
            out[m.group(1).strip()] = (int(m.group(2)), int(m.group(3)))
    return out


def fmt(stats: tuple[int, int] | None) -> str:
    if stats is None:
        return "—"
    correct, total = stats
    pct = correct / total * 100 if total else 0
    return f"{correct}/{total} ({pct:.0f}%)"


def main() -> int:
    if not SUMMARY_UK.is_file():
        print(f"ERROR: UK summary not found: {SUMMARY_UK}", file=sys.stderr)
        print("Run `python OD/indexing/evaluate_uk.py` first.", file=sys.stderr)
        return 2

    nodejs = parse_summary(SUMMARY_NODEJS.read_text()) if SUMMARY_NODEJS.is_file() else {}
    uk = parse_summary(SUMMARY_UK.read_text())

    labels = sorted(set(nodejs) | set(uk))
    width = max((len(s) for s in labels), default=20)

    print(f"\n{'Category':<{width}}  {'Node.js':>14}  {'UK Legal':>14}  Δ")
    print(f"{'-' * width}  {'-' * 14}  {'-' * 14}  --")
    for label in labels:
        n = nodejs.get(label)
        u = uk.get(label)
        delta = ""
        if n and u and n[1] and u[1]:
            delta_pp = (u[0] / u[1] - n[0] / n[1]) * 100
            sign = "+" if delta_pp >= 0 else ""
            delta = f"{sign}{delta_pp:.0f} pp"
        print(f"{label:<{width}}  {fmt(n):>14}  {fmt(u):>14}  {delta}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
