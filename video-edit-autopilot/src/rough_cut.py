# -*- coding: utf-8 -*-
"""rough_cut.py — propose, judge, merge, and apply a rough cut, no Editkin required.

Full pipeline for a NEW episode (raw transcript only, no final exists yet):

    1. learn (edit_style_model.py)   accumulate edit_style_profile.json from every
                                      pre/post pair you have -- more episodes, better profile
    2a. propose                      mechanical candidates: dead-air (audio silencedetect) +
                                      learned-filler (fuzzy text match vs. the profile)
    2b. tangent judgment              NOT mechanical -- an LLM reads the new raw transcript
        (see TANGENT_JUDGMENT_        against the profile's verified_real_cuts examples and
         RECIPE below)                writes tangent candidates in the same cuts.json schema.
                                      A tangent is defined by relevance to the topic at hand,
                                      not by wording, so no string-match rule can find it.
    3. merge                         combine 2a's file and 2b's file into one cuts.json
    4. human review                  open the merged cuts.json, delete anything wrong
    5. apply                         video + reviewed cuts.json -> rough-cut mp4

For footage that ALREADY has a real published edit (training data, not a new episode):

    reconstruct   raw transcript + final transcript -> exact cuts.json (character-level diff,
                  robust to the two transcripts chunking sentences differently -- see
                  edit_style_profile.md's methodology note for why block-level diff isn't safe
                  here). Feed the result's cut ranges back into edit_style_profile.json's
                  verified_real_cuts_* field so future tangent judgment has more calibration.

`cuts.json` is meant to be opened and edited before `apply` at every stage — delete any line
you disagree with. This kit's existing philosophy: audit before trusting a derived list (see
templates/audience_vocab.example.json).

TANGENT_JUDGMENT_RECIPE (step 2b, run by an LLM reading the transcript directly):
    1. Read the new episode's raw transcript.
    2. Read edit_style_profile.json's verified_real_cuts_* entries as calibration examples --
       what kinds of tangents this show/creator actually cuts (pre-roll banter, off-topic
       personal-life riffs that run long, negotiation/job asides, etc).
    3. If a pre-recording outline/talking-points doc exists for this episode, run the topic-
       adherence method (see profiles/ep6_part1_topic_adherence.md for the worked example) --
       segments that don't map to any planned topic and run long are the strongest tangent
       signal available.
    4. Write candidates as a cuts.json with the same schema propose() produces: each entry
       {"start": ..., "end": ..., "sources": ["tangent_judgment"], "evidence": ["why"]}.
    5. `merge` this file with propose()'s mechanical output before review.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from delivery_media_ops import _probe_dur, _run  # noqa: E402
from media_delivery_qa import build_keep_ranges, detect_long_pauses, trim_dead_air_ranges  # noqa: E402
from edit_style_model import Block, normalize, parse_transcript, select_canonical_blocks, ts_to_seconds  # noqa: E402

FUZZY_MATCH_THRESHOLD = 0.85


def _merge_ranges(ranges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by start and merge overlapping/touching cut ranges, unioning their evidence."""
    ordered = sorted(ranges, key=lambda r: r["start"])
    merged: list[dict[str, Any]] = []
    for r in ordered:
        if merged and r["start"] <= merged[-1]["end"] + 0.05:
            merged[-1]["end"] = max(merged[-1]["end"], r["end"])
            merged[-1]["sources"] = sorted(set(merged[-1]["sources"]) | set(r["sources"]))
            merged[-1]["evidence"].extend(r["evidence"])
        else:
            merged.append({**r, "sources": list(r["sources"]), "evidence": list(r["evidence"])})
    return merged


def propose_cuts(
    transcript_path: Path,
    video_path: Path,
    profile_path: Path | None,
    min_dead_air: float,
) -> dict[str, Any]:
    blocks = [b for b in parse_transcript(transcript_path) if b.canonical]
    total_dur = _probe_dur(video_path)

    candidates: list[dict[str, Any]] = []

    # -- dead air, from the real audio track --
    with tempfile.TemporaryDirectory() as td:
        wav_path = str(Path(td) / "audio.wav")
        r = _run(["ffmpeg", "-v", "error", "-y", "-i", str(video_path), "-vn",
                  "-ac", "1", "-ar", "16000", wav_path])
        if r.returncode != 0:
            raise RuntimeError("audio extraction failed: " + r.stderr[-600:])
        pauses = detect_long_pauses(wav_path, min_sec=min_dead_air)
    for start, end in trim_dead_air_ranges(pauses):
        candidates.append({
            "start": round(start, 3), "end": round(end, 3),
            "sources": ["dead_air"], "evidence": [f"{end - start:.1f}s silence"],
        })

    # -- learned filler/reaction lines --
    filler_texts: list[str] = []
    if profile_path and profile_path.is_file():
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        filler_texts = [item["text"] for item in profile.get("frequent_filler_or_reaction_cuts", [])]
    filler_norms = [normalize(t) for t in filler_texts]

    for b in blocks:
        key = normalize(b.canonical)
        if not key:
            continue
        best_ratio, best_text = 0.0, ""
        for norm, text in zip(filler_norms, filler_texts):
            ratio = SequenceMatcher(a=key, b=norm, autojunk=False).ratio()
            if ratio > best_ratio:
                best_ratio, best_text = ratio, text
        if best_ratio >= FUZZY_MATCH_THRESHOLD:
            candidates.append({
                "start": round(ts_to_seconds(b.start), 3),
                "end": round(ts_to_seconds(b.end), 3),
                "sources": ["learned_filler"],
                "evidence": [f"matches learned filler '{best_text}' ({best_ratio:.2f})"],
            })

    merged = _merge_ranges(candidates)
    cut_seconds = sum(c["end"] - c["start"] for c in merged)

    return {
        "_readme": (
            "Review every line before running `apply`. Delete anything you disagree with. "
            "'dead_air' is measured directly off your audio; 'learned_filler' is a fuzzy text "
            "match against edit_style_profile.json, not a certainty."
        ),
        "video": str(video_path),
        "transcript": str(transcript_path),
        "source_duration_sec": round(total_dur, 3),
        "proposed_cut_seconds": round(cut_seconds, 3),
        "estimated_output_duration_sec": round(total_dur - cut_seconds, 3),
        "cuts": merged,
    }


def _char_time_index(blocks: list[Block]) -> tuple[str, list[tuple[int, float, float]]]:
    """Concatenate every block's canonical text; return (text, [(end_char_idx, start_sec, end_sec), ...]).

    Used to map a character offset in the concatenated text back to a real timestamp by
    finding which block it falls in and interpolating linearly across that block's span.
    """
    concat_parts: list[str] = []
    index: list[tuple[int, float, float]] = []
    pos = 0
    for b in blocks:
        text = normalize(b.canonical)
        if not text:
            continue
        try:
            start, end = ts_to_seconds(b.start), ts_to_seconds(b.end)
        except ValueError:
            continue
        concat_parts.append(text)
        pos += len(text)
        index.append((pos, start, end))
    return "".join(concat_parts), index


def _char_to_time(char_idx: int, index: list[tuple[int, float, float]], at_end: bool) -> float:
    """Map a character offset to a real timestamp via linear interpolation within its block."""
    prev_end_idx, prev_start_sec = 0, index[0][1] if index else 0.0
    for end_idx, start_sec, end_sec in index:
        if char_idx <= end_idx:
            span_chars = max(end_idx - prev_end_idx, 1)
            frac = (char_idx - prev_end_idx) / span_chars
            return start_sec + frac * (end_sec - start_sec)
        prev_end_idx, prev_start_sec = end_idx, end_sec
    return index[-1][2] if index else 0.0


def reconstruct_cuts(pre_path: Path, post_path: Path) -> dict[str, Any]:
    """Build a precise, apply-ready cuts list for footage that already has a real edited version.

    Unlike edit_style_model's block-level diff (built for pattern-learning, where some noise
    from resegmentation is fine), this diffs the FULL CONCATENATED text character-by-character
    so a block boundary mismatch between the raw and final transcript's chunking never gets
    misread as a cut. Only content genuinely absent from the final transcript's text counts.
    Real timestamps come from linear interpolation within the raw transcript's own blocks.

    Two more failure modes, found by actually watching a reconstructed cut against the source:

    1. Same audio, different ASR garbling. An English name/proper noun embedded in Chinese
       speech can get transcribed completely differently in the raw pass vs. the final pass
       (e.g. "Olivia" heard as "我閨蜜啊簽" in one file and "Ovivia" in the other) -- text-level
       diff has no way to know these are the same word, and flags the raw version as cut when
       the real audio was actually kept. The tell: an isolated SHORT unmatched span sandwiched
       between two long, cleanly-matching passages, versus a genuine cut which tends to run
       seconds-to-minutes. MIN_CONFIDENT_CUT_SEC routes short spans to `low_confidence_cuts`
       for manual review instead of silently including them in the executable `cuts` list.
    2. Trailing artifacts at a cut boundary. ASR end-timestamps for laughter/reactions routinely
       land short of when the sound actually decays, leaving an audible sliver right at the join.
       END_PAD_SEC extends every confident cut's end slightly to absorb that.
    """
    MIN_CONFIDENT_CUT_SEC = 1.2
    END_PAD_SEC = 0.25

    pre_blocks = select_canonical_blocks(parse_transcript(pre_path))
    post_blocks = select_canonical_blocks(parse_transcript(post_path))

    pre_text, pre_index = _char_time_index(pre_blocks)
    post_text, _ = _char_time_index(post_blocks)

    sm = SequenceMatcher(a=pre_text, b=post_text, autojunk=False)
    cuts: list[dict[str, Any]] = []
    low_confidence: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag not in ("delete", "replace"):
            continue
        if i2 - i1 < 4:  # a handful of stray characters, not worth flagging at all
            continue
        start = _char_to_time(i1, pre_index, at_end=False)
        end = _char_to_time(i2, pre_index, at_end=True)
        if end - start < 0.3:
            continue
        if end - start < MIN_CONFIDENT_CUT_SEC:
            low_confidence.append({
                "start": round(start, 3), "end": round(end, 3),
                "sources": ["ground_truth_diff_short"],
                "evidence": [f"short + isolated, likely ASR mismatch not a real cut -- verify before including: {pre_text[i1:i2][:40]}"],
            })
            continue
        cuts.append({
            "start": round(start, 3), "end": round(end + END_PAD_SEC, 3),
            "sources": ["ground_truth_diff"],
            "evidence": [f"absent from published transcript: {pre_text[i1:i2][:40]}"],
        })

    merged = _merge_ranges(cuts)
    cut_seconds = sum(c["end"] - c["start"] for c in merged)
    source_dur = pre_index[-1][2] if pre_index else 0.0

    return {
        "_readme": (
            "Reconstructed from a real published edit, not a heuristic guess -- but still review "
            "before `apply`. Character-level diff avoids the resegmentation false-positives a "
            "block-level diff produces; verify a sample against the final transcript regardless. "
            "Short isolated spans are held out in low_confidence_cuts rather than auto-included -- "
            "review those separately before adding any of them to `cuts`."
        ),
        "pre_transcript": str(pre_path),
        "post_transcript": str(post_path),
        "source_duration_sec": round(source_dur, 3),
        "low_confidence_cuts": low_confidence,
        "proposed_cut_seconds": round(cut_seconds, 3),
        "estimated_output_duration_sec": round(source_dur - cut_seconds, 3),
        "cuts": merged,
    }


def merge_cuts_files(paths: list[Path]) -> dict[str, Any]:
    """Combine multiple cuts.json files (e.g. propose's mechanical output + a tangent-judgment
    file) into one, merging overlapping ranges and unioning their evidence/sources."""
    all_cuts: list[dict[str, Any]] = []
    sources_meta = []
    video = transcript = None
    source_duration = None
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        all_cuts.extend(data.get("cuts", []))
        sources_meta.append(str(p))
        video = video or data.get("video")
        transcript = transcript or data.get("transcript") or data.get("pre_transcript")
        if source_duration is None:
            source_duration = data.get("source_duration_sec")

    merged = _merge_ranges(all_cuts)
    cut_seconds = sum(c["end"] - c["start"] for c in merged)

    return {
        "_readme": "Merged from multiple cuts.json files. Review before `apply` -- merging does not imply approval.",
        "merged_from": sources_meta,
        "video": video,
        "transcript": transcript,
        "source_duration_sec": source_duration,
        "proposed_cut_seconds": round(cut_seconds, 3),
        "estimated_output_duration_sec": (round(source_duration - cut_seconds, 3) if source_duration else None),
        "cuts": merged,
    }


def cut_av_together(video_in: str, video_out: str, cuts: list[tuple[float, float]], end: float | None = None) -> str:
    """Remove the same time ranges from video and audio in one ffmpeg pass, staying in sync."""
    if end is None:
        end = _probe_dur(video_in)
    keep = build_keep_ranges(cuts, end)
    v_expr = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in keep)
    fc = (
        f"[0:v]select='{v_expr}',setpts=N/FRAME_RATE/TB[vout];"
        f"[0:a]aselect='{v_expr}',asetpts=N/SR/TB[aout]"
    )
    r = _run(["ffmpeg", "-v", "error", "-y", "-i", video_in,
              "-filter_complex", fc, "-map", "[vout]", "-map", "[aout]",
              "-c:v", "libx264", "-crf", "18", "-preset", "medium",
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", video_out])
    if r.returncode != 0:
        raise RuntimeError("cut_av_together failed: " + r.stderr[-800:])
    return video_out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("propose", help="derive cuts.json from a raw transcript + video")
    p.add_argument("--transcript", required=True)
    p.add_argument("--video", required=True)
    p.add_argument("--profile", default=None, help="path to edit_style_profile.json (optional)")
    p.add_argument("--min-dead-air", type=float, default=1.5, help="seconds of silence to flag (default 1.5)")
    p.add_argument("--out", required=True, help="output path for cuts.json")

    r = sub.add_parser("reconstruct", help="build a precise cuts.json from a raw+published transcript pair (footage that's already edited)")
    r.add_argument("--pre", required=True, help="raw transcript with real timestamps")
    r.add_argument("--post", required=True, help="published/final transcript with real timestamps")
    r.add_argument("--out", required=True, help="output path for cuts.json")

    m = sub.add_parser("merge", help="combine multiple cuts.json files (e.g. mechanical propose + tangent judgment) into one")
    m.add_argument("--in", dest="inputs", action="append", required=True, help="a cuts.json to merge; repeatable")
    m.add_argument("--out", required=True, help="output path for the merged cuts.json")

    a = sub.add_parser("apply", help="execute a reviewed cuts.json against the real video")
    a.add_argument("--video", required=True)
    a.add_argument("--cuts", required=True, help="path to a (reviewed) cuts.json from `propose`")
    a.add_argument("--out", required=True, help="output path for the rough-cut mp4")

    args = parser.parse_args()

    if args.command == "propose":
        result = propose_cuts(
            Path(args.transcript), Path(args.video),
            Path(args.profile) if args.profile else None,
            args.min_dead_air,
        )
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path}")
        print(f"source duration: {result['source_duration_sec']}s")
        print(f"proposed cuts: {len(result['cuts'])} ranges, {result['proposed_cut_seconds']}s total")
        print(f"estimated output duration: {result['estimated_output_duration_sec']}s")
        print("REVIEW cuts.json before running `apply` — nothing here is auto-approved.")
    elif args.command == "reconstruct":
        result = reconstruct_cuts(Path(args.pre), Path(args.post))
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path}")
        print(f"source duration: {result['source_duration_sec']}s")
        print(f"reconstructed cuts: {len(result['cuts'])} ranges, {result['proposed_cut_seconds']}s total")
        print(f"estimated output duration: {result['estimated_output_duration_sec']}s")
        print("REVIEW cuts.json before running `apply`.")
    elif args.command == "merge":
        result = merge_cuts_files([Path(p) for p in args.inputs])
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path}")
        print(f"merged {len(args.inputs)} files -> {len(result['cuts'])} ranges, {result['proposed_cut_seconds']}s total")
        print("REVIEW the merged cuts.json before running `apply`.")
    elif args.command == "apply":
        data = json.loads(Path(args.cuts).read_text(encoding="utf-8"))
        cuts = [(c["start"], c["end"]) for c in data["cuts"]]
        out = cut_av_together(args.video, args.out, cuts)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
