"""
Script 2 — auto-uploads an episode to Buzzsprout as a draft.

Per docs/production_playbook.md: takes the exported MP3 and script_01's
content markdown, creates a Buzzsprout episode via their REST API, and leaves
it as a draft for a human to review and publish.

NOT YET RUN AGAINST LIVE BUZZSPROUT CREDENTIALS — this is a scaffold built
directly from Buzzsprout's public API docs (https://www.buzzsprout.com/api),
not a verified integration. Test against a real (or sandbox) podcast before
trusting it with a real episode.

Usage:
    python scripts/script_02_buzzsprout_upload.py \\
        --audio episodes/ep1/ep1_final.mp3 \\
        --content episodes/ep1/episode_ep1_content.md

Requires BUZZSPROUT_API_KEY and BUZZSPROUT_PODCAST_ID in the environment
(see .env.example).
"""

import argparse
import os
import re
import sys
from pathlib import Path


def extract_section(content: str, heading: str) -> str:
    """Pulls the body of a `## Heading` section out of script_01's output markdown."""
    pattern = rf"## {re.escape(heading)}\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_title(content: str) -> str:
    """Uses the first title option from script_01's output as the episode title."""
    options = extract_section(content, "Title Options")
    first_line = next((ln.strip() for ln in options.splitlines() if ln.strip()), "")
    return re.sub(r"^\d+[.):]\s*", "", first_line).strip("\"'")


def upload_episode(audio_path: Path, title: str, description: str) -> dict:
    try:
        import requests
    except ImportError:
        print("Missing dependency: pip install -r requirements.txt (needs `requests`)", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("BUZZSPROUT_API_KEY")
    podcast_id = os.environ.get("BUZZSPROUT_PODCAST_ID")
    if not api_key or not podcast_id:
        print("BUZZSPROUT_API_KEY / BUZZSPROUT_PODCAST_ID not set — see .env.example.", file=sys.stderr)
        sys.exit(1)

    url = f"https://www.buzzsprout.com/api/{podcast_id}/episodes.json"
    headers = {"Authorization": f"Token token={api_key}"}
    with open(audio_path, "rb") as audio_file:
        files = {"audio_file": audio_file}
        data = {
            "title": title,
            "description": description,
            "published": "false",  # leave as draft — human reviews and publishes
        }
        response = requests.post(url, headers=headers, data=data, files=files, timeout=120)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", required=True, help="Path to the exported episode MP3")
    parser.add_argument("--content", required=True, help="Path to script_01's episode_<date>_content.md")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    content_path = Path(args.content)
    for p in (audio_path, content_path):
        if not p.exists():
            print(f"Not found: {p}", file=sys.stderr)
            sys.exit(1)

    content = content_path.read_text(encoding="utf-8")
    title = extract_title(content)
    description = extract_section(content, "Podcast Description")
    if not title or not description:
        print(
            "Could not find a title or podcast description in the content file — "
            "check it matches script_01's section headings.",
            file=sys.stderr,
        )
        sys.exit(1)

    result = upload_episode(audio_path, title, description)
    episode_url = result.get("episode_url") or result.get("full_url", "(no URL in response)")
    print(f"Draft created: {episode_url}")
    print("Review and publish manually in the Buzzsprout dashboard.")


if __name__ == "__main__":
    main()
