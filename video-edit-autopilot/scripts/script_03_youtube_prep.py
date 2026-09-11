"""
Script 3 — preps everything YouTube needs so upload is copy-paste.

Per docs/production_playbook.md: reads script_01's content markdown, validates
the chapter format YouTube requires, and writes a checklist with title,
description, tags, thumbnail brief, and target playlist. The actual YouTube
upload stays manual (Playbook flags API upload as a month-2+ upgrade).

Usage:
    python scripts/script_03_youtube_prep.py \\
        --content episodes/ep1/episode_ep1_content.md \\
        --episode-number 1 \\
        [--topic-keyword layoff]
"""

import argparse
import re
import sys
from pathlib import Path

CHAPTER_LINE_RE = re.compile(r"^(?:\d{1,2}:)?\d{1,2}:\d{2}\b")


def extract_section(content: str, heading: str) -> str:
    pattern = rf"## {re.escape(heading)}\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""


def validate_chapters(youtube_description: str) -> list[str]:
    """Returns a list of problems found with the chapter markers, empty if none."""
    problems = []
    chapter_lines = [
        ln for ln in youtube_description.splitlines() if CHAPTER_LINE_RE.match(ln.strip())
    ]
    if not chapter_lines:
        problems.append(
            "No chapter lines found in `HH:MM:SS`/`MM:SS`-at-line-start format — "
            "YouTube won't auto-render chapters without this."
        )
        return problems
    if not chapter_lines[0].strip().startswith(("0:00", "00:00")):
        problems.append(
            f"First chapter is `{chapter_lines[0].strip()}`, not 0:00 — "
            "YouTube requires the first chapter to start at 0:00."
        )
    if len(chapter_lines) < 3:
        problems.append(
            f"Only {len(chapter_lines)} chapter(s) found — YouTube requires at least 3 "
            "for chapters to render."
        )
    return problems


def build_checklist(content: str, episode_number: str, topic_keyword: str | None) -> str:
    titles = extract_section(content, "Title Options")
    first_title = next((ln.strip() for ln in titles.splitlines() if ln.strip()), "(no title found)")
    first_title = re.sub(r"^\d+[.):]\s*", "", first_title).strip("\"'")

    youtube_description = extract_section(content, "YouTube Description")
    chapter_problems = validate_chapters(youtube_description)

    thumbnail_brief = (
        f"Episode {episode_number}"
        + (f" — keyword: {topic_keyword}" if topic_keyword else "")
        + "\nSuggested text overlay: pull the sharpest line from the pull quotes below."
        " Use CapCut/Canva branded template."
    )

    pull_quotes = extract_section(content, "Pull Quotes")

    lines = [
        f"# YouTube Upload Checklist — Episode {episode_number}",
        "",
        "## Title",
        first_title,
        "",
        "## Description (paste as-is)",
        "```",
        youtube_description,
        "```",
    ]

    if chapter_problems:
        lines += ["", "## ⚠ Chapter format problems — fix before uploading"]
        lines += [f"- {p}" for p in chapter_problems]

    lines += [
        "",
        "## Tags",
        "career reinvention, layoff, immigrant women in tech, career coaching, "
        "data analytics career, The Long Way Here",
        "",
        "## Thumbnail brief",
        thumbnail_brief,
        "",
        "## Playlist",
        "Episodes",
        "",
        "## Pull quotes (for community post / clips)",
        pull_quotes,
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", required=True, help="Path to script_01's episode_<date>_content.md")
    parser.add_argument("--episode-number", required=True)
    parser.add_argument("--topic-keyword", default=None)
    parser.add_argument("--out", default=None, help="Output path (default: youtube_upload_checklist.md next to the content file)")
    args = parser.parse_args()

    content_path = Path(args.content)
    if not content_path.exists():
        print(f"Not found: {content_path}", file=sys.stderr)
        sys.exit(1)

    content = content_path.read_text(encoding="utf-8")
    checklist = build_checklist(content, args.episode_number, args.topic_keyword)

    out_path = Path(args.out) if args.out else content_path.parent / "youtube_upload_checklist.md"
    out_path.write_text(checklist, encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
