"""
Script 1 — transcript in, all written content out.

Per docs/production_playbook.md: reads a Riverside transcript, sends it to the
Claude API with a structured prompt, and writes a single markdown file with
five outputs: title options, show notes, YouTube description with chapters,
podcast description, and pull quotes.

Run this against the *edited* transcript (the transcript of the CapCut
export), not the raw Riverside download — see docs/editing_learnings.md for
why. If you only have the raw download, run scripts/prep_transcript.py on it
first to check it isn't partly mis-transcribed.

Usage:
    python scripts/script_01_text_outputs.py \\
        --transcript episodes/ep1/ep1_post.srt \\
        --episode-number 1 \\
        --episode-date 2026-09-01 \\
        [--guest-name "Nina Tseng"] \\
        [--out episodes/ep1/episode_ep1_content.md]

Requires ANTHROPIC_API_KEY in the environment (see .env.example).
"""

import argparse
import os
import sys
from pathlib import Path

PROMPT_TEMPLATE = """\
You are producing the written content package for an episode of "The Long Way \
Here", a podcast/YouTube show by two co-hosts (Olivia Pan and Nina Tseng) about \
career reinvention for immigrant women in tech and data — analytics, AI, \
consulting, coaching, career pivots. The audience is mid-to-senior immigrant \
women navigating layoffs, career transitions, and rebuilding on their own \
terms. Tone: direct, warm, a little dry-humored, zero corporate-LinkedIn \
gloss. The hosts code-switch between Mandarin and English mid-sentence — \
that's normal for this show, not an error in the transcript.

Episode number: {episode_number}
{guest_line}
Full transcript (post-edit, timestamps reflect the published cut):
---
{transcript}
---

Produce exactly five sections, each under its own markdown heading, in this \
order:

## Title Options
Three options. Punchy, specific to what's actually discussed (not generic \
"career journey" language), audience-aware.

## Show Notes
~200 words. Cover who's on the episode, what topics are covered, one honest \
detail that makes someone want to listen, and a CTA.

## YouTube Description
Full YouTube description with a timestamped chapter list auto-detected from \
topic shifts in the transcript. Chapter timestamps must be formatted \
`HH:MM:SS` or `MM:SS` at the start of the line (YouTube's requirement).

## Podcast Description
~100 words, for Buzzsprout. Shorter and punchier than the show notes, not a \
copy-paste of it.

## Pull Quotes
Three quotes pulled verbatim (or lightly cleaned of filler words, meaning \
preserved) from the transcript, each attributed to the speaker who said it.
"""


def build_prompt(transcript: str, episode_number: str, guest_name: str | None) -> str:
    guest_line = f"Guest: {guest_name}" if guest_name else ""
    return PROMPT_TEMPLATE.format(
        episode_number=episode_number,
        guest_line=guest_line,
        transcript=transcript,
    )


def call_claude(prompt: str) -> str:
    try:
        import anthropic
    except ImportError:
        print(
            "Missing dependency: pip install -r requirements.txt (needs `anthropic`)",
            file=sys.stderr,
        )
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY is not set — see .env.example.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(
        block.text for block in response.content if block.type == "text"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", required=True, help="Path to the transcript file")
    parser.add_argument("--episode-number", required=True)
    parser.add_argument("--episode-date", required=True, help="YYYY-MM-DD, used in the output filename")
    parser.add_argument("--guest-name", default=None)
    parser.add_argument("--out", default=None, help="Output path (default: episode_<date>_content.md next to the transcript)")
    args = parser.parse_args()

    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        print(f"Transcript not found: {transcript_path}", file=sys.stderr)
        sys.exit(1)

    transcript = transcript_path.read_text(encoding="utf-8")
    prompt = build_prompt(transcript, args.episode_number, args.guest_name)
    output = call_claude(prompt)

    out_path = Path(args.out) if args.out else transcript_path.parent / f"episode_{args.episode_date}_content.md"
    out_path.write_text(output, encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
