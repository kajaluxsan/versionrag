#!/usr/bin/env python3
"""Evaluate + score the UK Legal corpus against OD/dataset/eval_set.csv.

Runs `scripts/evaluate.py` then `scripts/score.py` with UK-specific
input/output paths, then renames the auto-generated summary file to
`evaluation_summary_uk.txt` (since score.py hardcodes the summary path).

Usage:
    python OD/indexing/evaluate_uk.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAG_ROOT = HERE.parent.parent / "version-aware-RAG"
EVAL_SET = HERE.parent / "dataset" / "eval_set.csv"
RESULTS_DIR = RAG_ROOT / "data" / "results"

ANSWERS_UK = RESULTS_DIR / "evaluation_answers_uk.csv"
SCORED_UK = RESULTS_DIR / "evaluation_scored_uk.csv"
SUMMARY_AUTO = RESULTS_DIR / "evaluation_summary.txt"  # written by score.py
SUMMARY_UK = RESULTS_DIR / "evaluation_summary_uk.txt"


def run(cmd: list[str]) -> int:
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=RAG_ROOT).returncode


def main() -> int:
    if not EVAL_SET.is_file():
        print(f"ERROR: eval set not found: {EVAL_SET}", file=sys.stderr)
        return 2

    # --- 1. Run evaluation (questions → /query → answers CSV) ---
    rc = run([
        "uv", "run", "python", "scripts/evaluate.py",
        "--input", str(EVAL_SET),
        "--output", str(ANSWERS_UK),
    ])
    if rc != 0:
        print(f"\nERROR: evaluate.py exited {rc}", file=sys.stderr)
        return rc

    # --- 2. Run scoring (answers → LLM-as-judge → scored CSV + summary) ---
    rc = run([
        "uv", "run", "python", "scripts/score.py",
        "--input", str(ANSWERS_UK),
        "--output", str(SCORED_UK),
    ])
    if rc != 0:
        print(f"\nERROR: score.py exited {rc}", file=sys.stderr)
        return rc

    # --- 3. score.py wrote summary to evaluation_summary.txt — rename it ---
    if SUMMARY_AUTO.is_file():
        shutil.move(str(SUMMARY_AUTO), str(SUMMARY_UK))
        print(f"\nMoved {SUMMARY_AUTO.name} → {SUMMARY_UK.name}")
    else:
        print(f"\nWARN: expected {SUMMARY_AUTO} not found", file=sys.stderr)

    print(f"\n{'=' * 60}")
    print("UK EVALUATION COMPLETE")
    print(f"{'=' * 60}")
    print(f"Answers : {ANSWERS_UK}")
    print(f"Scored  : {SCORED_UK}")
    print(f"Summary : {SUMMARY_UK}")
    if SUMMARY_UK.is_file():
        print()
        print(SUMMARY_UK.read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main())
