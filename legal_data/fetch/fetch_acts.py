#!/usr/bin/env python3
"""Fetch the last N point-in-time versions of UK Acts as Markdown.

Reads ``acts.txt`` next to this script (one Act per line:
``{type} {year} {number}``), discovers each Act's full version list from
its CLML index XML via ``<atom:link rel="...hasVersion">`` entries, picks
the N most recent dated versions, fetches each as HTML and converts it
to Markdown using ``markdownify``.

Output: ``OD/documents/{type}-{year}-{number}_{YYYY-MM-DD}.md``
Log:    ``OD/fetch/fetch.log`` (alongside this script)

The script is idempotent — files that already exist are skipped, so an
interrupted run can be resumed by simply running the script again.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path
from typing import Iterator

import requests
from bs4 import BeautifulSoup
from lxml import etree
from markdownify import markdownify
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ACTS_FILE = SCRIPT_DIR / "acts.txt"
DEFAULT_LOG_FILE = SCRIPT_DIR / "fetch.log"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR.parent / "documents"

USER_AGENT = "VersionRAG-BA-Research (kmathitharan@gmail.com)"
BASE_URL = "https://www.legislation.gov.uk"
DATE_RE = re.compile(r"/(\d{4}-\d{2}-\d{2})$")

logger = logging.getLogger("fetch_acts")


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


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def parse_acts(acts_file: Path) -> Iterator[tuple[str, str, str, str]]:
    """Yield (type, year, number, title) for each non-comment line."""
    for raw in acts_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts, _, title = line.partition("#")
        tokens = parts.split()
        if len(tokens) < 3:
            logger.warning("Skipping malformed line: %s", raw)
            continue
        yield tokens[0], tokens[1], tokens[2], title.strip()


def fetch_versions(
    session: requests.Session, act_type: str, year: str, number: str
) -> list[tuple[str, str]]:
    """Return [(date, url)] of all dated point-in-time versions, newest first."""
    url = f"{BASE_URL}/{act_type}/{year}/{number}/data.xml"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    root = etree.fromstring(resp.content)
    hrefs = root.xpath(
        "//*[local-name()='link']"
        "[@rel='http://purl.org/dc/terms/hasVersion']/@href"
    )
    versions: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href in hrefs:
        match = DATE_RE.search(href)
        if not match:
            continue
        date = match.group(1)
        if date in seen:
            continue
        seen.add(date)
        versions.append((date, href))
    versions.sort(key=lambda x: x[0], reverse=True)
    return versions


def fetch_markdown(session: requests.Session, version_url: str) -> str:
    """Fetch the HTML rendering of a legislation page and convert to clean Markdown."""
    resp = session.get(
        version_url,
        headers={"Accept": "application/xhtml+xml,text/html;q=0.9"},
        timeout=60,
    )
    resp.raise_for_status()
    return html_to_markdown(resp.text)


# IDs of legislation.gov.uk page chrome that wrap navigation, search, tabs,
# breadcrumbs, cookie banners, print options, etc. — none of these contain
# the actual Act text and must be removed before Markdown conversion.
CHROME_IDS = {
    "primaryNav", "contentSearch", "breadcrumb", "breadcrumbNav",
    "printOptions", "openingOptions", "advFeatures", "whatversion",
    "moreResources", "moreResourcesPrintOptions", "timeline", "timelineHelp",
    "searchChanges", "statusWarning", "statusWarningSubSections",
    "cookieBanner", "cookieMessage", "cookies", "skipLinks", "skiplinks",
    "Scenario5Help", "advFeaturesHelp", "openingOptionsHelp",
    "moreResourcesTabHelp", "whatversionHelp", "interpretationHelp",
    "footer", "globalHeader", "globalFooter",
}

CHROME_CLASSES = {"cookieMessage", "cookies", "skiplinks", "help",
                  "interpretation", "footer", "header", "navigation"}

# CSS selectors of likely legislation-content containers, in priority order.
CONTENT_SELECTORS = [
    "#viewLegSnippet",
    "#viewLegContents",
    "#content",
    "#mainContent",
    "main",
    "article",
]


def html_to_markdown(html: str) -> str:
    """Extract the legislation snippet from a legislation.gov.uk page and
    convert it to clean Markdown — strips scripts, navigation, cookie banner,
    breadcrumbs, tab widgets, footer, and help-icon images."""
    soup = BeautifulSoup(html, "html.parser")

    # Drop wholesale tag categories that are never part of the Act text.
    for tag in soup.find_all([
        "script", "style", "noscript", "form",
        "header", "footer", "nav", "aside",
        "iframe", "meta", "link",
    ]):
        tag.decompose()

    # Drop known chrome containers by id.
    for cid in CHROME_IDS:
        for el in soup.find_all(id=cid):
            el.decompose()

    # Drop known chrome containers by class.
    for cls in CHROME_CLASSES:
        for el in soup.find_all(class_=cls):
            el.decompose()

    # Strip help-icon images and the <a> tags that wrap them — these
    # produce things like `[![ Help about...](/images/chrome/helpIcon.gif)](#...)`
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if (
            "/images/chrome/" in src
            or "/images/crests/" in src
            or "helpIcon" in src
            or "closeIcon" in src
        ):
            parent = img.parent
            if parent and parent.name == "a":
                parent.decompose()
            else:
                img.decompose()

    # Strip title= attributes from <a> tags — markdownify renders them as
    # `[text](url "title")`, and on legislation.gov.uk the title is just
    # "Go to <repeat of link text>", which doubles token count for no value.
    for a in soup.find_all("a"):
        if a.has_attr("title"):
            del a["title"]

    # Pick the most specific container that holds the Act text.
    main = None
    for sel in CONTENT_SELECTORS:
        main = soup.select_one(sel)
        if main is not None:
            break
    if main is None:
        main = soup.body or soup

    md = markdownify(
        str(main),
        heading_style="ATX",
        strip=["script", "style"],
    )
    return postprocess(md)


# Lines whose entire content is page-chrome text — drop them.
JUNK_LINE_PATTERNS = [
    r"^\s*Skip to (?:main content|navigation)\s*$",
    r"^\s*Cookies on legislation\.gov\.uk\s*$",
    r"^\s*Accept all cookies\s*$",
    r"^\s*Reject all cookies\s*$",
    r"^\s*Set cookie preferences\s*$",
    r"^\s*Print Options\s*$",
    r"^\s*Previous\s*$",
    r"^\s*Next\s*$",
    r"^\s*Back to top\s*$",
    r"^\s*\[Back to top\].*$",
    r"^\s*View more\s*$",
    r"^\s*Plain View\s*$",
    r"^\s*Show Geographical Extent.*$",
    r"^\s*Show Timeline of Changes.*$",
]


def postprocess(md: str) -> str:
    """Trim residual junk lines and collapse excessive blank lines."""
    for p in JUNK_LINE_PATTERNS:
        md = re.sub(p, "", md, flags=re.MULTILINE)
    # Drop residual help-icon Markdown that survived if any
    md = re.sub(r"\[!\[\s*Help[^\]]*\]\([^\)]*\)\]\([^\)]*\)", "", md)
    # Collapse 3+ consecutive blank lines into 2
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n"


def output_path(
    output_dir: Path, act_type: str, year: str, number: str, date: str
) -> Path:
    return output_dir / f"{act_type}-{year}-{number}_{date}.md"


def process_act(
    session: requests.Session,
    act_type: str,
    year: str,
    number: str,
    title: str,
    output_dir: Path,
    max_versions: int,
    sleep_s: float,
) -> tuple[int, int]:
    """Fetch up to max_versions for one Act. Returns (saved, skipped)."""
    label = f"{act_type} {year} {number}"
    logger.info("→ %s (%s)", label, title or "no title")

    try:
        versions = fetch_versions(session, act_type, year, number)
    except Exception as exc:
        logger.error("✗ %s — version list fetch failed: %s", label, exc)
        return 0, 0

    if not versions:
        logger.warning(
            "⚠ %s — no dated point-in-time versions found", label
        )
        return 0, 0

    chosen = versions[:max_versions]
    if len(chosen) < max_versions:
        logger.warning(
            "⚠ %s — only %d dated versions available (asked for %d)",
            label, len(chosen), max_versions,
        )

    saved = skipped = 0
    for date, url in chosen:
        out = output_path(output_dir, act_type, year, number, date)
        if out.exists():
            logger.info("  · %s — already exists, skipping", out.name)
            skipped += 1
            continue
        try:
            md = fetch_markdown(session, url)
        except Exception as exc:
            logger.error(
                "  ✗ %s @ %s — fetch failed: %s", label, date, exc
            )
            continue
        if len(md) < 2048:
            logger.warning(
                "  ⚠ %s @ %s — markdown looks small (%d bytes)",
                label, date, len(md),
            )
        out.write_text(md, encoding="utf-8")
        logger.info("  ✓ %s saved (%d bytes)", out.name, len(md))
        saved += 1
        time.sleep(sleep_s)

    logger.info("✓ %s — %d saved, %d skipped", label, saved, skipped)
    return saved, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch UK legislation point-in-time versions as Markdown."
    )
    parser.add_argument("--acts-file", type=Path, default=DEFAULT_ACTS_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE)
    parser.add_argument("--max-versions", type=int, default=5)
    parser.add_argument("--sleep", type=float, default=1.0)
    args = parser.parse_args()

    setup_logging(args.log_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if not args.acts_file.exists():
        logger.error("acts file not found: %s", args.acts_file)
        return 2

    acts = list(parse_acts(args.acts_file))
    logger.info(
        "Starting fetch: %d acts, max %d versions each, output=%s",
        len(acts), args.max_versions, args.output_dir,
    )

    session = make_session()
    total_saved = total_skipped = 0
    for act_type, year, number, title in acts:
        saved, skipped = process_act(
            session, act_type, year, number, title,
            args.output_dir, args.max_versions, args.sleep,
        )
        total_saved += saved
        total_skipped += skipped

    logger.info(
        "Done. %d acts processed, %d files saved, %d skipped (existed)",
        len(acts), total_saved, total_skipped,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
