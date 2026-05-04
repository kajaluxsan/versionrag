#!/usr/bin/env python3
"""Generate a 150-row legal-domain evaluation set via `claude -p`.

Loops over 30 Acts × 5 query types = 150 (act, type) pairs. For each pair,
loads the matching prompt template from ``prompts/{type}.md``, builds the
type-specific input (one version, all version dates, or a diff between
two versions), invokes ``claude -p`` as a subprocess, parses the returned
JSON ``{"question": ..., "answer": ...}`` and appends a row to the
deliverable CSV. A sidecar progress CSV in OD/generation/ tracks which
(act, type) pairs have been completed so the script is resumable.

Inputs:
- ``OD/documents/{type}-{year}-{number}_{date}.md`` (Markdown, from fetch step)
- ``OD/fetch/acts.txt`` (canonical list of 30 Acts)
- ``OD/generation/prompts/{type}.md`` (one prompt per query type)

Outputs:
- ``OD/dataset/eval_set.csv``         (deliverable; columns: Type, Question, Answer)
- ``OD/generation/.progress.csv``     (resume tracking; columns: ActID, Type)
- ``OD/generation/generation.log``    (timestamped run log)
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DOCS_DIR = SCRIPT_DIR.parent / "documents"
DEFAULT_ACTS_FILE = SCRIPT_DIR.parent / "fetch" / "acts.txt"
DEFAULT_PROMPTS_DIR = SCRIPT_DIR / "prompts"
DEFAULT_OUTPUT_CSV = SCRIPT_DIR.parent / "dataset" / "eval_set.csv"
DEFAULT_PROGRESS_CSV = SCRIPT_DIR / ".progress.csv"
DEFAULT_LOG_FILE = SCRIPT_DIR / "generation.log"

# (csv_type_label, internal_type_id, prompt_file_stem)
TYPES: list[tuple[str, str]] = [
    ("Content Retrieval", "content_retrieval"),
    ("Version-Specific Content Retrieval", "content_version_specific"),
    ("Version Listing & Inquiry", "version_listing"),
    ("Change Retrieval (e)", "change_retrieval_explicit"),
    ("Change Retrieval (i)", "change_retrieval_implicit"),
]

MAX_DOC_CHARS = 12000
MAX_DIFF_CHARS = 8000
MAX_DIFF_CHARS_PER_TRANSITION = 3000
DOC_FILENAME_RE = re.compile(
    r"^(?P<act_id>[a-z]+-\d{4}-\d+)_(?P<date>\d{4}-\d{2}-\d{2})\.md$"
)

logger = logging.getLogger("generate_eval")


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_acts(acts_file: Path) -> list[tuple[str, str]]:
    """Parse acts.txt → [(act_id, title)] preserving file order."""
    acts: list[tuple[str, str]] = []
    for raw in acts_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        body, _, title = line.partition("#")
        tokens = body.split()
        if len(tokens) < 3:
            continue
        act_id = f"{tokens[0]}-{tokens[1]}-{tokens[2]}"
        acts.append((act_id, title.strip()))
    return acts


def load_documents(docs_dir: Path) -> dict[str, list[tuple[str, str]]]:
    """Group .md files by act_id → [(date, content), ...] sorted asc by date."""
    by_act: dict[str, list[tuple[str, str]]] = {}
    for md_path in sorted(docs_dir.glob("*.md")):
        match = DOC_FILENAME_RE.match(md_path.name)
        if not match:
            logger.warning("Skipping unparseable filename: %s", md_path.name)
            continue
        act_id = match.group("act_id")
        date = match.group("date")
        content = md_path.read_text(encoding="utf-8")
        by_act.setdefault(act_id, []).append((date, content))
    for act_id in by_act:
        by_act[act_id].sort(key=lambda x: x[0])
    return by_act


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars - head - 50
    return text[:head] + "\n\n[... TRUNCATED ...]\n\n" + text[-tail:]


def compute_diff(text_old: str, text_new: str, max_chars: int) -> str:
    """Compact unified diff between two texts."""
    diff = difflib.unified_diff(
        text_old.splitlines(keepends=False),
        text_new.splitlines(keepends=False),
        fromfile="old", tofile="new", n=2,
    )
    diff_text = "\n".join(diff)
    if not diff_text.strip():
        return "(no textual differences detected)"
    return truncate(diff_text, max_chars)


def build_input(
    qtype: str, act_id: str, title: str, sorted_docs: list[tuple[str, str]]
) -> dict[str, Any]:
    """Build the input payload for the prompt, depending on query type."""
    if qtype == "content_retrieval":
        date, content = sorted_docs[-1]
        return {
            "act_title": title or act_id,
            "version_date": date,
            "content": truncate(content, MAX_DOC_CHARS),
        }
    if qtype == "content_version_specific":
        idx = len(sorted_docs) // 2 if len(sorted_docs) > 1 else 0
        date, content = sorted_docs[idx]
        return {
            "act_title": title or act_id,
            "version_date": date,
            "content": truncate(content, MAX_DOC_CHARS),
        }
    if qtype == "version_listing":
        return {
            "act_title": title or act_id,
            "version_dates": [d for d, _ in sorted_docs],
        }
    if qtype == "change_retrieval_explicit":
        if len(sorted_docs) < 2:
            raise ValueError(
                f"{act_id}: need ≥2 versions for {qtype}, have {len(sorted_docs)}"
            )
        old_date, old_content = sorted_docs[0]
        new_date, new_content = sorted_docs[-1]
        return {
            "act_title": title or act_id,
            "version_from": old_date,
            "version_to": new_date,
            "diff": compute_diff(old_content, new_content, MAX_DIFF_CHARS),
        }
    if qtype == "change_retrieval_implicit":
        if len(sorted_docs) < 2:
            raise ValueError(
                f"{act_id}: need ≥2 versions for {qtype}, have {len(sorted_docs)}"
            )
        # Per-transition diffs so the LLM can localize a change to one specific
        # (from→to) step rather than collapsing everything into oldest→newest.
        transitions = []
        for i in range(1, len(sorted_docs)):
            prev_date, prev_content = sorted_docs[i - 1]
            curr_date, curr_content = sorted_docs[i]
            transitions.append({
                "from": prev_date,
                "to": curr_date,
                "diff": compute_diff(prev_content, curr_content,
                                     MAX_DIFF_CHARS_PER_TRANSITION),
            })
        return {
            "act_title": title or act_id,
            "version_dates": [d for d, _ in sorted_docs],
            "transitions": transitions,
        }
    raise ValueError(f"Unknown query type: {qtype}")


def render_prompt(prompts_dir: Path, qtype: str, input_data: dict[str, Any]) -> str:
    template = (prompts_dir / f"{qtype}.md").read_text(encoding="utf-8")
    input_json = json.dumps(input_data, indent=2, ensure_ascii=False)
    return template.replace("{input_json}", input_json)


def call_claude(prompt: str, timeout_s: int = 300) -> str:
    """Run `claude -p PROMPT` and return stdout text."""
    proc = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True, text=True, timeout=timeout_s,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude -p exited {proc.returncode}: {proc.stderr[:500]}"
        )
    return proc.stdout


def extract_qa(response: str) -> dict[str, str]:
    """Pull a {"question":..., "answer":...} JSON object out of Claude's output."""
    text = response.strip()
    # Strip optional markdown code-fence wrapping
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    # Find the first JSON object greedily but balanced
    start = text.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in response: {response[:200]}")
    depth = 0
    end = -1
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end == -1:
        raise ValueError(f"Unbalanced JSON in response: {response[:200]}")
    obj = json.loads(text[start:end + 1])
    if not isinstance(obj, dict) or "question" not in obj or "answer" not in obj:
        raise ValueError(f"Missing 'question'/'answer' keys in: {obj}")
    return {"question": str(obj["question"]).strip(),
            "answer": str(obj["answer"]).strip()}


def load_existing_rows(progress_path: Path) -> set[tuple[str, str]]:
    """Return set of (act_id, csv_type) recorded in the progress sidecar CSV."""
    if not progress_path.exists():
        return set()
    done: set[tuple[str, str]] = set()
    with progress_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row.get("ActID", ""), row.get("Type", ""))
            if key[0] and key[1]:
                done.add(key)
    return done


def append_row(
    output_csv: Path,
    progress_csv: Path,
    csv_type: str,
    question: str,
    answer: str,
    act_id: str,
) -> None:
    """Append the QA pair to eval_set.csv (3 cols) and progress.csv (2 cols)."""
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    progress_csv.parent.mkdir(parents=True, exist_ok=True)

    new_output = not output_csv.exists()
    with output_csv.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Type", "Question", "Answer"])
        if new_output:
            writer.writeheader()
        writer.writerow({"Type": csv_type, "Question": question, "Answer": answer})

    new_progress = not progress_csv.exists()
    with progress_csv.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ActID", "Type"])
        if new_progress:
            writer.writeheader()
        writer.writerow({"ActID": act_id, "Type": csv_type})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-dir", type=Path, default=DEFAULT_DOCS_DIR)
    parser.add_argument("--acts-file", type=Path, default=DEFAULT_ACTS_FILE)
    parser.add_argument("--prompts-dir", type=Path, default=DEFAULT_PROMPTS_DIR)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--progress-csv", type=Path, default=DEFAULT_PROGRESS_CSV,
                        help="Sidecar CSV used to track resume state")
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE)
    parser.add_argument("--sleep", type=float, default=0.5,
                        help="Sleep between claude calls")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit total (act,type) generations (for testing)")
    args = parser.parse_args()

    setup_logging(args.log_file)

    if not args.acts_file.exists():
        logger.error("acts file not found: %s", args.acts_file)
        return 2
    if not args.documents_dir.exists():
        logger.error("documents dir not found: %s", args.documents_dir)
        return 2
    if not args.prompts_dir.exists():
        logger.error("prompts dir not found: %s", args.prompts_dir)
        return 2

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    acts = load_acts(args.acts_file)
    docs_by_act = load_documents(args.documents_dir)
    done = load_existing_rows(args.progress_csv)
    logger.info(
        "Loaded %d acts, %d acts with documents, %d rows already done",
        len(acts), len(docs_by_act), len(done),
    )

    total_target = len(acts) * len(TYPES)
    generated = skipped = failed = 0

    for act_id, title in acts:
        sorted_docs = docs_by_act.get(act_id, [])
        if not sorted_docs:
            logger.warning("⚠ %s — no documents found, skipping all types", act_id)
            continue

        for csv_type, internal_type in TYPES:
            if args.limit is not None and generated >= args.limit:
                logger.info("Reached --limit=%d, stopping", args.limit)
                break

            key = (act_id, csv_type)
            if key in done:
                logger.info("· %s [%s] — already in csv, skipping", act_id, csv_type)
                skipped += 1
                continue

            try:
                input_data = build_input(internal_type, act_id, title, sorted_docs)
            except ValueError as exc:
                logger.warning("⚠ %s [%s] — %s", act_id, csv_type, exc)
                failed += 1
                continue

            prompt = render_prompt(args.prompts_dir, internal_type, input_data)
            logger.info("→ %s [%s] (prompt %d chars)", act_id, csv_type, len(prompt))

            try:
                response = call_claude(prompt)
                qa = extract_qa(response)
            except Exception as exc:
                logger.error("✗ %s [%s] — %s", act_id, csv_type, exc)
                failed += 1
                continue

            append_row(
                args.output_csv,
                args.progress_csv,
                csv_type=csv_type,
                question=qa["question"],
                answer=qa["answer"],
                act_id=act_id,
            )
            done.add(key)
            generated += 1
            logger.info(
                "✓ %s [%s] (%d/%d)", act_id, csv_type, generated + skipped, total_target
            )
            time.sleep(args.sleep)

        if args.limit is not None and generated >= args.limit:
            break

    logger.info(
        "Done. generated=%d, skipped=%d, failed=%d, target=%d",
        generated, skipped, failed, total_target,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
