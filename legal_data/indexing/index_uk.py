#!/usr/bin/env python3
"""Index the UK Legal Markdown corpus (OD/documents/) via the running API.

Thin wrapper around `version-aware-RAG/scripts/index.py`. The actual prompt
swap is configured via the env-vars VERSIONRAG_EXTRACT_PROMPT and
VERSIONRAG_QUERY_PROMPT — set them in version-aware-RAG/.env BEFORE starting
the server (`make start`), since the server reads the env at module-import
time.

Usage:
    python OD/indexing/index_uk.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAG_ROOT = HERE.parent.parent / "version-aware-RAG"
DOCS_DIR = HERE.parent / "documents"
EXTRACT_PROMPT = HERE / "prompts" / "extract_attributes.md"
QUERY_PROMPT = HERE / "prompts" / "query_parser.md"


def main() -> int:
    if not DOCS_DIR.is_dir():
        print(f"ERROR: documents directory not found: {DOCS_DIR}", file=sys.stderr)
        return 2

    if not EXTRACT_PROMPT.is_file() or not QUERY_PROMPT.is_file():
        print("ERROR: prompt files missing under OD/indexing/prompts/", file=sys.stderr)
        return 2

    # Sanity-check the env vars the running server should have picked up
    expected_extract = str(EXTRACT_PROMPT)
    expected_query = str(QUERY_PROMPT)
    actual_extract = os.environ.get("VERSIONRAG_EXTRACT_PROMPT", "")
    actual_query = os.environ.get("VERSIONRAG_QUERY_PROMPT", "")
    if actual_extract != expected_extract or actual_query != expected_query:
        print(
            "WARN: env-vars VERSIONRAG_EXTRACT_PROMPT / VERSIONRAG_QUERY_PROMPT\n"
            "      are not set to the OD/indexing/prompts/ paths in *this* shell.\n"
            "      That's fine if the server (make start) has them set in *its* env\n"
            "      via .env — the server is what actually loads the prompts.\n"
            f"      Expected extract: {expected_extract}\n"
            f"      Expected query:   {expected_query}\n"
        )

    print(f"Indexing UK corpus from: {DOCS_DIR}")
    print(f"  Documents found: {len(list(DOCS_DIR.glob('*.md')))}")
    print()

    # Trigger indexing via the existing CLI
    cmd = [
        "uv", "run", "python", "scripts/index.py",
        "--data-dir", str(DOCS_DIR),
    ]
    proc = subprocess.run(cmd, cwd=RAG_ROOT)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
