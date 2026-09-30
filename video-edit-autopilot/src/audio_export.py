# -*- coding: utf-8 -*-
"""audio_export.py — extract a podcast-platform-ready audio master from the final video.

Production Playbook Phase E calls for "audio-only (MP3, 192kbps) from the same CapCut
project" alongside the video export -- this is that step, run against whatever this pipeline
produced instead of a manual CapCut export, so it stays scriptable end to end.

Usage:
    python src/audio_export.py --video branded.mp4 --out episode.mp3
"""
from __future__ import annotations

import argparse
import subprocess


def _run(args: list[str]) -> None:
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(args)}\n{r.stderr[-4000:]}")


def export_audio(video: str, out: str, bitrate: str = "192k") -> str:
    _run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn",
          "-c:a", "libmp3lame", "-b:a", bitrate, out])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--out", required=True, help="output .mp3 path")
    parser.add_argument("--bitrate", default="192k")
    args = parser.parse_args()
    out = export_audio(args.video, args.out, bitrate=args.bitrate)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
