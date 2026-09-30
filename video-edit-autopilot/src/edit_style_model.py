# -*- coding: utf-8 -*-
"""edit_style_model.py — learn a creator's cut/retention style from pre/post transcript pairs.

Public, generic, reusable by anyone. It does NOT execute cuts — there is no
shipped executor in this kit (see profiles/EDITKIN_STATUS.md). It converts
raw-vs-final transcript pairs into a reviewable style brief: what gets cut,
what gets fixed, what gets added, and how much survives. That brief is meant
to be handed to a human editor (or a future AI cutting step) as a spec for
"how this creator edits" — the same way profiles/voice.md specs "how this
creator writes."

Input format (per pair): two plain-text transcripts in SRT-like blocks —

    <index>
    <start> --> <end>
    <text line 1>
    [<text line 2> ...]
    <blank line>

One block may carry a single language (raw-source-language pre/post pairs)
or multiple lines per block (bilingual pre/post pairs). Only the block's
CJK-dominant line is used for alignment — translation lines ride along for
context but never drive the diff, so both layouts work unmodified.

Nothing here is hardcoded to any one creator's vocabulary. Every derived
list is ranked by *frequency observed in your own pairs* — per this kit's
existing philosophy (see templates/audience_vocab.example.json): audited
from your own transcripts, never copied from someone else's.

Diffs on the full concatenated transcript text, character by character, not
block-by-block (see rough_cut.py's reconstruct_cuts, which this mirrors) --
a raw ASR pass and a human-cleaned pass routinely chunk the same sentence
into different-sized blocks, and comparing block-to-block reads every one of
those boundary shifts as a false cut. MIN_CONFIDENT_CUT_SEC/CHAR_MIN_CONFIDENT_CUT
drop spans too short to be anything but ASR noise or a homophone mismatch;
TANGENT_MIN_SEC is a calibration knob, not a universal constant -- recheck it
against your own footage once you have more pairs.

CLI:
    python src/edit_style_model.py learn \\
        --pair raw1.txt=final1.txt --pair raw2.txt=final2.txt \\
        --out profiles/edit_style_profile

Writes <out>.json (machine-readable) and <out>.md (human review checklist).
Add more --pair entries any time and re-run; the profile is not additive
across runs by itself — feed it every pair you have each time (kept simple
on purpose; merge logic can be added once there's a real second creator
using this beyond a single run).
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2  # v2: char-level diff (see diff_pair); per_pair now reports chars, not blocks
CJK_RE = re.compile(r"[一-鿿]")
SHORT_BLOCK_CHARS = 8         # <= this many "words" -> candidate filler/reaction, not content
CHAR_MIN_CONFIDENT_CUT = 4    # shorter char spans are stray/noise, not a cut worth reporting
MIN_CONFIDENT_CUT_SEC = 1.2   # shorter time spans are likely ASR/homophone mismatch, not a real cut
TANGENT_MIN_SEC = 8.0         # cut spans at least this long are a tangent, not a filler/reaction word


@dataclass
class Block:
    index: int
    start: str
    end: str
    lines: list[str]

    @property
    def canonical(self) -> str:
        """The line most likely to be the raw-speech line, not its translation."""
        if not self.lines:
            return ""
        best = max(self.lines, key=lambda ln: len(CJK_RE.findall(ln)))
        cjk_hits = len(CJK_RE.findall(best))
        return best if cjk_hits > 0 else self.lines[0]

    @property
    def all_text(self) -> str:
        return " / ".join(self.lines)


def parse_transcript(path: Path) -> list[Block]:
    raw = path.read_text(encoding="utf-8")
    blocks: list[Block] = []
    chunk: list[str] = []

    def flush(chunk: list[str]) -> None:
        if len(chunk) < 2:
            return
        idx_line = chunk[0].strip()
        ts_line = chunk[1].strip()
        m = re.match(r"^(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})$", ts_line)
        if not idx_line.isdigit() or not m:
            return
        text_lines = [ln.strip() for ln in chunk[2:] if ln.strip()]
        blocks.append(Block(index=int(idx_line), start=m.group(1), end=m.group(2), lines=text_lines))

    for line in raw.splitlines():
        if line.strip() == "":
            flush(chunk)
            chunk = []
        else:
            chunk.append(line)
    flush(chunk)
    return blocks


def ts_to_seconds(ts: str) -> float:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s.replace(",", "."))


def normalize(text: str) -> str:
    text = re.sub(r"[，。！？、,.!?~…\-—\s]+", "", text)
    return text.lower()


@dataclass
class PairReport:
    pair_name: str
    pre_total: int   # pre-transcript block count (display only)
    matched: int     # matched characters -- see diff_pair
    pre_chars: int = 0
    retention_ratio: float = 0.0
    filler_or_reaction_cuts: list[str] = field(default_factory=list)
    tangent_cuts: list[dict[str, Any]] = field(default_factory=list)
    content_cuts: list[str] = field(default_factory=list)
    rewrites: list[dict[str, str]] = field(default_factory=list)
    added_hook: list[str] = field(default_factory=list)
    added_other: list[str] = field(default_factory=list)
    cut_ranges: list[tuple[float, float]] = field(default_factory=list)


def select_canonical_blocks(blocks: list[Block]) -> list[Block]:
    """Drop pure-translation blocks in language-segmented transcripts.

    Some transcripts interleave languages per block (bilingual: every block
    has both a CJK line and an English line); others segment by language
    (sequential: a run of CJK-only blocks, then a run of English-only
    blocks covering the same content, or vice versa). In the segmented
    case, the non-dominant-language blocks are pure translations of blocks
    that already exist elsewhere in the same file and must be dropped
    before diffing, or they show up as false "added content" against the
    other transcript. Detected via what fraction of blocks contain any CJK
    character at all.
    """
    cjk_containing = [b for b in blocks if CJK_RE.search(b.all_text)]
    cjk_ratio = len(cjk_containing) / len(blocks) if blocks else 0.0
    if 0 < cjk_ratio < 1:
        # Mixed: CJK is present but not universal -> language-segmented file.
        # Keep only the CJK-bearing blocks as the raw-speech signal.
        return [b for b in cjk_containing if b.canonical]
    # Either every block has CJK (bilingual-per-block, canonical already
    # picks the CJK line) or none do (pure non-CJK source language).
    return [b for b in blocks if b.canonical]


def _handle_insert(run: list[Block], global_j_start: int, report: PairReport) -> None:
    for offset, b in enumerate(run):
        if global_j_start + offset <= 3:
            report.added_hook.append(b.canonical)
        else:
            report.added_other.append(b.canonical)


def _char_time_index(blocks: list[Block]) -> tuple[str, list[tuple[int, int, float, float, Block]]]:
    """Concatenate every block's normalized text into one string and index
    each contiguous char span back to its timestamp range and source block.

    Diffing this string (see diff_pair) instead of the block list itself is
    what makes the result immune to resegmentation: the same sentence can
    land in one block in the raw ASR pass and three blocks in the cleaned
    pass without ever registering as a cut, because the character stream is
    identical either way -- only the span boundaries move."""
    parts: list[str] = []
    index: list[tuple[int, int, float, float, Block]] = []
    pos = 0
    for b in blocks:
        text = normalize(b.canonical)
        if not text:
            continue
        try:
            start, end = ts_to_seconds(b.start), ts_to_seconds(b.end)
        except ValueError:
            continue
        parts.append(text)
        index.append((pos, pos + len(text), start, end, b))
        pos += len(text)
    return "".join(parts), index


def _char_to_time(char_idx: int, index: list[tuple[int, int, float, float, Block]]) -> float:
    if not index:
        return 0.0
    for start_char, end_char, start_sec, end_sec, _ in index:
        if char_idx <= end_char:
            span = max(end_char - start_char, 1)
            frac = (char_idx - start_char) / span
            return start_sec + frac * (end_sec - start_sec)
    return index[-1][3]


def _blocks_for_span(index: list[tuple[int, int, float, float, Block]], i1: int, i2: int) -> list[Block]:
    return [b for start_char, end_char, _, _, b in index if end_char > i1 and start_char < i2]


def diff_pair(pre_path: Path, post_path: Path) -> PairReport:
    pre_blocks = select_canonical_blocks(parse_transcript(pre_path))
    post_blocks = select_canonical_blocks(parse_transcript(post_path))

    pre_text, pre_index = _char_time_index(pre_blocks)
    post_text, post_index = _char_time_index(post_blocks)

    report = PairReport(
        pair_name=f"{pre_path.name}->{post_path.name}",
        pre_total=len(pre_blocks),
        matched=0,
        retention_ratio=0.0,
    )

    matched_chars = 0
    sm = SequenceMatcher(a=pre_text, b=post_text, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            matched_chars += i2 - i1
            continue
        if tag == "insert":
            _handle_insert(_blocks_for_span(post_index, j1, j2), j1, report)
            continue

        # "delete" or "replace": the pre span [i1,i2) is missing (or reworded) in post.
        pre_span_blocks = _blocks_for_span(pre_index, i1, i2)
        if not pre_span_blocks:
            continue
        span_chars = i2 - i1
        post_span_chars = j2 - j1

        if tag == "replace" and post_span_chars >= span_chars * 0.4:
            # Comparable length on both sides -> a genuine rewrite (typo,
            # homophone, phrasing fix), not a cut.
            report.rewrites.append({
                "pre": "".join(b.canonical for b in pre_span_blocks),
                "post": "".join(b.canonical for b in _blocks_for_span(post_index, j1, j2)),
            })
            matched_chars += min(span_chars, post_span_chars)
            continue

        start_sec = _char_to_time(i1, pre_index)
        end_sec = _char_to_time(i2, pre_index)
        span_sec = end_sec - start_sec
        if span_chars < CHAR_MIN_CONFIDENT_CUT or span_sec < MIN_CONFIDENT_CUT_SEC:
            continue  # too short/isolated to trust -- ASR noise or a homophone mismatch, not a real cut

        report.cut_ranges.append((start_sec, end_sec))
        if span_sec >= TANGENT_MIN_SEC:
            report.tangent_cuts.append({
                "blocks": len(pre_span_blocks),
                "preview": " | ".join(b.canonical for b in pre_span_blocks[:3]) + (" ..." if len(pre_span_blocks) > 3 else ""),
                "full_text": [b.canonical for b in pre_span_blocks],
            })
        else:
            for b in pre_span_blocks:
                if len(b.canonical) <= SHORT_BLOCK_CHARS:
                    report.filler_or_reaction_cuts.append(b.canonical)
                else:
                    report.content_cuts.append(b.canonical)
        if tag == "replace":
            _handle_insert(_blocks_for_span(post_index, j1, j2), j1, report)

    report.matched = matched_chars
    report.pre_chars = len(pre_text)
    report.retention_ratio = round(matched_chars / report.pre_chars, 3) if report.pre_chars else 0.0

    return report


def build_profile(reports: list[PairReport]) -> dict[str, Any]:
    filler_counter: Counter[str] = Counter()
    for r in reports:
        filler_counter.update(r.filler_or_reaction_cuts)

    avg_retention = round(sum(r.retention_ratio for r in reports) / len(reports), 3) if reports else 0.0

    def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # A block straddling two adjacent diff opcodes can get attributed to
        # both (see _blocks_for_span's overlap test) -- same finding reported
        # twice back to back. Order-preserving dedupe on the full entry (json
        # key, not tuple(sorted(...)), since values here include lists).
        seen: set[str] = set()
        out = []
        for item in items:
            key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    return {
        "_readme": (
            "Derived cut/retention style profile. Every list here is ranked by frequency "
            "observed in the pairs you fed it — audit before trusting, same rule as "
            "templates/audience_vocab.example.json. Nothing is invented."
        ),
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pairs_analyzed": [r.pair_name for r in reports],
        "avg_retention_ratio": avg_retention,
        "frequent_filler_or_reaction_cuts": [
            {"text": text, "seen_in_pairs": count} for text, count in filler_counter.most_common(30)
        ],
        "tangent_cuts_for_review": _dedupe(
            [{"pair": r.pair_name, **t} for r in reports for t in r.tangent_cuts]
        ),
        "single_line_content_cuts_for_review": _dedupe(
            [{"pair": r.pair_name, "text": t} for r in reports for t in r.content_cuts]
        ),
        "rewrites_for_review": _dedupe(
            [{"pair": r.pair_name, **rw} for r in reports for rw in r.rewrites]
        ),
        "added_hooks_for_review": [
            {"pair": r.pair_name, "text": t} for r in reports for t in r.added_hook
        ],
        "added_other_for_review": [
            {"pair": r.pair_name, "text": t} for r in reports for t in r.added_other
        ],
        "per_pair": [
            {
                "pair": r.pair_name,
                "pre_blocks": r.pre_total,
                "pre_chars": r.pre_chars,
                "matched_chars": r.matched,
                "retention_ratio": r.retention_ratio,
            }
            for r in reports
        ],
    }


def render_markdown(profile: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Edit style profile (derived — review before trusting)\n")
    lines.append(f"Generated: {profile['generated_at']}\n")
    lines.append(f"Pairs analyzed: {', '.join(profile['pairs_analyzed']) or '(none)'}\n")
    lines.append(f"Average retention ratio (final / raw blocks): **{profile['avg_retention_ratio']}**\n")

    lines.append("\n## Frequent filler/reaction cuts (candidates — keep only what's real filler for you)\n")
    if profile["frequent_filler_or_reaction_cuts"]:
        for item in profile["frequent_filler_or_reaction_cuts"]:
            lines.append(f"- `{item['text']}` — cut in {item['seen_in_pairs']} pair(s)")
    else:
        lines.append("- (none found)")

    lines.append("\n## Tangent cuts (whole segments removed — label each, e.g. 'off-topic riff')\n")
    if profile["tangent_cuts_for_review"]:
        for t in profile["tangent_cuts_for_review"]:
            lines.append(f"- [{t['pair']}] {t['blocks']} blocks: {t['preview']}")
    else:
        lines.append("- (none found)")

    lines.append("\n## Single-line content cuts (ambiguous — review each)\n")
    if profile["single_line_content_cuts_for_review"]:
        for c in profile["single_line_content_cuts_for_review"]:
            lines.append(f"- [{c['pair']}] {c['text']}")
    else:
        lines.append("- (none found)")

    lines.append("\n## Rewrites / corrections (raw -> final)\n")
    if profile["rewrites_for_review"]:
        for rw in profile["rewrites_for_review"]:
            lines.append(f"- [{rw['pair']}] `{rw['pre']}` -> `{rw['post']}`")
    else:
        lines.append("- (none found)")

    lines.append("\n## Added hooks (new lines at the very top of the final cut)\n")
    if profile["added_hooks_for_review"]:
        for a in profile["added_hooks_for_review"]:
            lines.append(f"- [{a['pair']}] {a['text']}")
    else:
        lines.append("- (none found)")

    lines.append("\n## Added elsewhere (rare — check these aren't parsing artifacts)\n")
    if profile["added_other_for_review"]:
        for a in profile["added_other_for_review"]:
            lines.append(f"- [{a['pair']}] {a['text']}")
    else:
        lines.append("- (none found)")

    lines.append("\n## Per-pair stats\n")
    lines.append("| pair | raw blocks | raw chars | matched chars | retention |")
    lines.append("|---|---|---|---|---|")
    for p in profile["per_pair"]:
        lines.append(f"| {p['pair']} | {p['pre_blocks']} | {p['pre_chars']} | {p['matched_chars']} | {p['retention_ratio']} |")

    lines.append(
        "\n---\nThis profile is a brief, not an executor. Hand it to whoever/whatever cuts your "
        "footage (a human editor, or a future automation step) the same way profiles/voice.md "
        "is a brief for whoever writes your scripts.\n"
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    learn = sub.add_parser("learn", help="derive an edit-style profile from pre/post transcript pairs")
    learn.add_argument("--pair", action="append", required=True, metavar="RAW=FINAL",
                        help="path to raw transcript = path to final/published transcript; repeatable")
    learn.add_argument("--out", required=True, help="output path stem (writes <out>.json and <out>.md)")

    args = parser.parse_args()

    if args.command == "learn":
        reports = []
        for pair_arg in args.pair:
            if "=" not in pair_arg:
                raise SystemExit(f"--pair must be RAW=FINAL, got: {pair_arg}")
            raw_str, final_str = pair_arg.split("=", 1)
            reports.append(diff_pair(Path(raw_str), Path(final_str)))

        profile = build_profile(reports)
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        json_path = out_path.with_suffix(".json")
        if json_path.is_file():
            # Preserve any top-level fields this function doesn't generate itself (manually
            # curated additions like human_reviewed_corrections, methodology_notes, etc.) --
            # `learn` owns and overwrites only the keys it produces, never the whole file.
            existing = json.loads(json_path.read_text(encoding="utf-8"))
            for key, value in existing.items():
                if key not in profile:
                    profile[key] = value
        json_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md_path = out_path.with_suffix(".md")
        md_text = render_markdown(profile)
        if md_path.is_file():
            old_md = md_path.read_text(encoding="utf-8")
            marker = "\n---\nThis profile is a brief, not an executor."
            if marker in old_md:
                appended = old_md.split(marker, 1)[1]
                md_text = md_text.rstrip("\n") + "\n" + marker.lstrip("\n") + appended
        md_path.write_text(md_text, encoding="utf-8")
        print(f"wrote {out_path.with_suffix('.json')}")
        print(f"wrote {out_path.with_suffix('.md')}")
        print(f"avg retention ratio: {profile['avg_retention_ratio']}")


if __name__ == "__main__":
    main()
