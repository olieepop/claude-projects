# -*- coding: utf-8 -*-
"""brand_insert.py — prepend/append brand material (intro, outro) to the rough-cut video.

Neither source kit has this: video-autopilot-kit's filter_runtime.py does grades and
transitions *within* a single clip, and rough_cut.py only removes ranges from one clip --
nothing stitches separately-produced brand assets onto the edited episode. Handles mismatched
codecs/resolutions/frame rates by re-encoding every input to one target spec before
concatenating (the file-list concat demuxer requires identical codecs; this doesn't).

Usage:
    python src/brand_insert.py --main cut.mp4 --intro intro.mp4 --outro outro.mp4 \
        --out branded.mp4
    python src/brand_insert.py --main cut.mp4 --intro intro.mp4 --out branded.mp4  # no outro
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def _run(args: list[str]) -> None:
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(args)}\n{r.stderr[-4000:]}")


def concat_with_brand(
    main: str,
    out: str,
    intro: str | None = None,
    outro: str | None = None,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    audio_rate: int = 48000,
) -> str:
    clips = [c for c in (intro, main, outro) if c]
    if len(clips) < 2:
        raise ValueError("need at least --main plus one of --intro/--outro")

    filter_parts = []
    concat_inputs = []
    for i, clip in enumerate(clips):
        filter_parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{i}];"
            f"[{i}:a]aresample={audio_rate},aformat=channel_layouts=stereo[a{i}]"
        )
        concat_inputs.append(f"[v{i}][a{i}]")
    filter_complex = ";".join(filter_parts) + ";" + "".join(concat_inputs)
    filter_complex += f"concat=n={len(clips)}:v=1:a=1[outv][outa]"

    cmd = ["ffmpeg", "-v", "error", "-y"]
    for clip in clips:
        cmd += ["-i", clip]
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        out,
    ]
    _run(cmd)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", required=True, help="the edited episode (rough_cut.py apply output)")
    parser.add_argument("--intro", help="brand intro clip, prepended")
    parser.add_argument("--outro", help="brand outro clip, appended")
    parser.add_argument("--out", required=True)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=30)
    args = parser.parse_args()

    out = concat_with_brand(
        args.main, args.out, intro=args.intro, outro=args.outro,
        width=args.width, height=args.height, fps=args.fps,
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
