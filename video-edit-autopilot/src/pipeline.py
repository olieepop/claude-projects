# -*- coding: utf-8 -*-
"""pipeline.py — the one new orchestration step: turn a reviewed rough cut into all four
deliverables (edited video, edited audio, captions, transcript) in one command.

Deliberately does NOT wrap propose / reconstruct / merge / apply (rough_cut.py) or learn
(edit_style_model.py) -- those already exist, already work without Editkin, and both source
kits are explicit that a human reviews cuts.json between propose and apply. Re-running them
from here would just be indirection around a tool that already has its own CLI. This module
starts *after* that review, at the point neither kit had automated: brand material, a final
audio master, and a transcript that actually matches the edited output.

Usage (video is rough_cut.py apply's output -- already-reviewed cuts applied):
    python src/pipeline.py finish \\
        --video rough_cut.mp4 --cuts cuts.json --raw-transcript raw.srt \\
        --intro assets/intro.mp4 --outro assets/outro.mp4 \\
        --captions captions.json --out-dir out/ep8/

--captions is optional (JSON array of {start,end,zh_clean,en} from your translation step, the
same shape dual_subtitle.py build expects). Without it you still get video/audio/transcript,
just no captions.srt. Pass --burn to also hard-burn captions into the video instead of leaving
that to a CapCut review pass (the default, matching this kit's existing captions workflow).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audio_export import export_audio  # noqa: E402
from brand_insert import concat_with_brand  # noqa: E402
from dual_subtitle import build_dual_ass, build_dual_srt, burn_subtitles  # noqa: E402
from final_transcript import build_final_transcript, load_cuts, write_srt  # noqa: E402
from edit_style_model import parse_transcript  # noqa: E402


def finish(
    video: str,
    cuts_path: str,
    raw_transcript: str,
    out_dir: str,
    intro: str | None = None,
    outro: str | None = None,
    captions_json: str | None = None,
    burn: bool = False,
) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    produced: dict[str, str] = {}

    branded = str(out / "video.mp4")
    if intro or outro:
        concat_with_brand(video, branded, intro=intro, outro=outro)
    else:
        shutil.copyfile(video, branded)
    produced["video"] = branded

    if captions_json:
        entries = json.loads(Path(captions_json).read_text(encoding="utf-8"))
        srt_path = out / "captions.srt"
        build_dual_srt(entries, srt_path)
        produced["captions_srt"] = str(srt_path)
        if burn:
            ass_path = out / "captions.ass"
            build_dual_ass(entries, ass_path)
            captioned = str(out / "video_captioned.mp4")
            burn_subtitles(branded, str(ass_path), captioned)
            produced["video_captioned"] = captioned

    audio_path = out / "audio.mp3"
    export_audio(produced.get("video_captioned", branded), str(audio_path))
    produced["audio"] = str(audio_path)

    blocks = parse_transcript(Path(raw_transcript))
    cuts = load_cuts(Path(cuts_path))
    entries = build_final_transcript(blocks, cuts)
    transcript_path = out / "transcript.srt"
    write_srt(entries, transcript_path)
    produced["transcript"] = str(transcript_path)

    return produced


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    f = sub.add_parser("finish", help="brand + audio + transcript (+ optional captions) from a reviewed rough cut")
    f.add_argument("--video", required=True, help="rough_cut.py apply's output")
    f.add_argument("--cuts", required=True, help="the cuts.json used for that apply (for transcript remap)")
    f.add_argument("--raw-transcript", required=True)
    f.add_argument("--out-dir", required=True)
    f.add_argument("--intro")
    f.add_argument("--outro")
    f.add_argument("--captions", help="captions JSON: [{start,end,zh_clean,en}, ...]")
    f.add_argument("--burn", action="store_true", help="hard-burn captions instead of leaving a CapCut-ready .srt")
    args = parser.parse_args()

    if args.command == "finish":
        produced = finish(
            video=args.video, cuts_path=args.cuts, raw_transcript=args.raw_transcript,
            out_dir=args.out_dir, intro=args.intro, outro=args.outro,
            captions_json=args.captions, burn=args.burn,
        )
        print("produced:")
        for k, v in produced.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
