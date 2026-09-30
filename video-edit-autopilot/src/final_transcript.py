# -*- coding: utf-8 -*-
"""final_transcript.py — the raw transcript, filtered and time-remapped onto the edited video.

Neither source kit produces this: rough_cut.py's cuts.json says what to remove from the
*video*, but nothing turns that same cut list back into a transcript that matches the
*output*. This is the missing "transcript" deliverable in the raw-video-in/four-outputs-out
pipeline (edited video, edited audio, caption, transcript).

Drops any transcript block that falls inside a cut range (or straddles one, split at the
boundary), then remaps every remaining timestamp with media_delivery_qa.remap_time so the
result lines up with rough_cut.py apply's output, not the raw footage.

Usage:
    python src/final_transcript.py --raw raw.srt --cuts cuts.json --out final_transcript.srt
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edit_style_model import Block, parse_transcript, ts_to_seconds  # noqa: E402
from media_delivery_qa import remap_time  # noqa: E402


def _fmt_ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = round((t - int(t)) * 1000)
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def load_cuts(cuts_path: Path) -> list[tuple[float, float]]:
    data = json.loads(cuts_path.read_text(encoding="utf-8"))
    return [(c["start"], c["end"]) for c in data["cuts"]]


def overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def build_final_transcript(blocks: list[Block], cuts: list[tuple[float, float]]) -> list[dict]:
    """Keep the portion of each block outside every cut range; drop a block entirely if a
    cut covers it end to end. A block only partly inside a cut keeps its surviving edge --
    good enough for a transcript (not a captions track, where sub-block splitting would
    actually matter)."""
    out: list[dict] = []
    for b in blocks:
        start, end = ts_to_seconds(b.start), ts_to_seconds(b.end)
        dur = end - start
        cut_dur = sum(overlap(start, end, cs, ce) for cs, ce in cuts)
        if dur <= 0 or cut_dur >= dur - 0.05:
            continue  # fully (or almost fully) cut
        new_start = remap_time(start, cuts)
        new_end = remap_time(end, cuts)
        if new_end <= new_start:
            continue
        out.append({"start": new_start, "end": new_end, "text": "\n".join(b.lines)})
    return out


def write_srt(entries: list[dict], out_path: Path) -> int:
    blocks = []
    for i, e in enumerate(entries, start=1):
        blocks.append(f"{i}\n{_fmt_ts(e['start'])} --> {_fmt_ts(e['end'])}\n{e['text']}\n")
    out_path.write_text("\n".join(blocks) + "\n", encoding="utf-8")
    return len(entries)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, help="raw transcript (.srt, real timestamps)")
    parser.add_argument("--cuts", required=True, help="reviewed cuts.json from rough_cut.py")
    parser.add_argument("--out", required=True, help="output .srt, remapped to the edited timeline")
    args = parser.parse_args()

    blocks = parse_transcript(Path(args.raw))
    cuts = load_cuts(Path(args.cuts))
    entries = build_final_transcript(blocks, cuts)
    n = write_srt(entries, Path(args.out))
    print(f"wrote {args.out} ({n} blocks, {len(blocks) - n} dropped by cuts)")


if __name__ == "__main__":
    main()
