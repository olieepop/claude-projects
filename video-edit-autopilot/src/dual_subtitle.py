# -*- coding: utf-8 -*-
"""dual_subtitle.py — build and burn a two-line (Traditional Chinese top / English below)
subtitle track with a solid black background and white text.

Input: a JSON array of {"start": sec, "end": sec, "zh_clean": "...", "en": "..."} entries —
see rough_cut.py's kept-block extraction + translation pass for how that gets built for a
freshly cut episode. Times are relative to the ALREADY-CUT video (post-`apply`), not the raw
source -- remap through media_delivery_qa.remap_time first if you're starting from raw-footage
timestamps.

Two output formats from the same `build` command, picked by your --out extension:

  --out foo.ass   ffmpeg's format, for `burn` (hard-codes captions into the video directly,
                  no further review step).
  --out foo.srt   Plain two-line SRT (Traditional Chinese line, English line below), for
                  importing into CapCut as an editable caption track -- load this alongside
                  the rough-cut video, review/adjust captions visually inside CapCut itself,
                  then export the final video from there instead of using `burn`.

Follows this kit's existing ASS convention (src/longform_maker/word_captions.py ASS_HEAD):
PlayResX/Y 1920x1080, BorderStyle=3 (opaque box, not just an outline), white primary text.
This module's style differs only in being fully opaque (not the ~30%-alpha box used for
single-language longform captions) and stacking two languages in one dialogue block via \\N.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ASS_HEAD = (
    "[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n"
    "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, "
    "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
    "Alignment, MarginL, MarginR, MarginV, Encoding\n"
    # Solid black box (BorderStyle=3 -> OutlineColour fills the box), fully opaque (&H00 alpha),
    # white text. Two languages share one style; the English line gets a smaller inline \fs tag.
    "Style: Bilingual,Heiti TC,60,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,3,14,0,2,120,120,80,1\n\n"
    "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)

EN_FONTSIZE = 40


def _ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _ts_srt(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = round((t - int(t)) * 1000)
    if ms == 1000:  # rounding carry
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _escape(text: str) -> str:
    return text.replace("{", "(").replace("}", ")")


def build_dual_ass(entries: list[dict[str, Any]], out_path: Path) -> int:
    """entries: [{"start", "end", "zh_clean", "en"}, ...] -> writes an ASS file. Returns line count."""
    lines = []
    for e in entries:
        zh = _escape(e["zh_clean"])
        en = _escape(e["en"])
        text = f"{zh}\\N{{\\fs{EN_FONTSIZE}}}{en}"
        lines.append(f"Dialogue: 0,{_ts(e['start'])},{_ts(e['end'])},Bilingual,,0,0,0,,{text}")
    out_path.write_text(ASS_HEAD + "\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


def build_dual_srt(entries: list[dict[str, Any]], out_path: Path) -> int:
    """entries: [{"start", "end", "zh_clean", "en"}, ...] -> writes a plain 2-line SRT
    (Traditional Chinese line, English line below). No styling -- CapCut applies its own
    caption-track font/box when you import this, which is the point: you review/adjust the
    actual wording and timing inside CapCut before it ever gets hard-burned. Returns cue count."""
    blocks = []
    for i, e in enumerate(entries, start=1):
        blocks.append(
            f"{i}\n{_ts_srt(e['start'])} --> {_ts_srt(e['end'])}\n{e['zh_clean']}\n{e['en']}\n"
        )
    out_path.write_text("\n".join(blocks) + "\n", encoding="utf-8")
    return len(entries)


def burn_subtitles(video_in: str, ass_path: str, video_out: str) -> str:
    """Hard-burn the ASS track into the video (single ffmpeg pass, re-encodes video, copies audio)."""
    ass_escaped = str(Path(ass_path).resolve()).replace("\\", "/").replace(":", "\\:")
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", video_in,
         "-vf", f"subtitles='{ass_escaped}'",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium",
         "-pix_fmt", "yuv420p", "-c:a", "copy", video_out],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError("burn_subtitles failed: " + r.stderr[-1000:])
    return video_out


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser(
        "build",
        help="build a caption file from a translated captions JSON -- .ass (for `burn`) or .srt (for CapCut import/review), picked by --out's extension",
    )
    b.add_argument("--captions", required=True, help="JSON array of {start,end,zh_clean,en}")
    b.add_argument("--out", required=True, help="output path: foo.ass (burn-ready) or foo.srt (CapCut-ready)")

    r = sub.add_parser("burn", help="burn an ASS file into a video (skip this if you're reviewing/exporting in CapCut instead)")
    r.add_argument("--video", required=True)
    r.add_argument("--ass", required=True)
    r.add_argument("--out", required=True)

    args = parser.parse_args()
    if args.command == "build":
        entries = json.loads(Path(args.captions).read_text(encoding="utf-8"))
        out_path = Path(args.out)
        if out_path.suffix.lower() == ".srt":
            n = build_dual_srt(entries, out_path)
        else:
            n = build_dual_ass(entries, out_path)
        print(f"wrote {out_path} ({n} lines)")
    elif args.command == "burn":
        out = burn_subtitles(args.video, args.ass, args.out)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
