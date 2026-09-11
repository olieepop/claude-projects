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

SCHEMA_VERSION = 1
CJK_RE = re.compile(r"[一-鿿]")
SHORT_BLOCK_CHARS = 8     # <= this many "words" -> candidate filler/reaction, not content
TANGENT_RUN_MIN = 3       # >= this many consecutive removed blocks -> candidate tangent


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
    pre_total: int
    matched: int
    retention_ratio: float
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


def _handle_delete(run: list[Block], report: PairReport) -> None:
    try:
        report.cut_ranges.append((ts_to_seconds(run[0].start), ts_to_seconds(run[-1].end)))
    except (ValueError, IndexError):
        pass
    if len(run) >= TANGENT_RUN_MIN:
        report.tangent_cuts.append({
            "blocks": len(run),
            "preview": " | ".join(b.canonical for b in run[:3]) + (" ..." if len(run) > 3 else ""),
            "full_text": [b.canonical for b in run],
        })
    else:
        for b in run:
            if len(b.canonical) <= SHORT_BLOCK_CHARS:
                report.filler_or_reaction_cuts.append(b.canonical)
            else:
                report.content_cuts.append(b.canonical)


def _handle_insert(run: list[Block], global_j_start: int, report: PairReport) -> None:
    for offset, b in enumerate(run):
        if global_j_start + offset <= 3:
            report.added_hook.append(b.canonical)
        else:
            report.added_other.append(b.canonical)


def _walk(
    pre_run: list[Block],
    post_run: list[Block],
    global_j_start: int,
    report: PairReport,
    depth: int = 0,
) -> int:
    """Return matched-block count; append findings to report as it goes.

    Recurses into oversized/mismatched "replace" spans so a genuine bulk
    cut (e.g. a whole tangent trimmed down to one bridging line) isn't
    force-paired position-by-position into nonsense "rewrites" — it finds
    the real small overlap first and reports the rest as cuts/additions.
    """
    if not pre_run:
        _handle_insert(post_run, global_j_start, report)
        return 0
    if not post_run:
        _handle_delete(pre_run, report)
        return 0

    def _base_case() -> None:
        if len(pre_run) == len(post_run):
            # Clean 1:1 swap -> genuine rewrite pairs (typo/homophone fixes).
            for p, q in zip(pre_run, post_run):
                report.rewrites.append({"pre": p.canonical, "post": q.canonical})
        else:
            # Sizes differ with no further internal overlap found -> an
            # honest bulk cut plus separately whatever appeared new, rather
            # than pretending a false position-by-position correspondence.
            _handle_delete(pre_run, report)
            _handle_insert(post_run, global_j_start, report)

    if depth >= 4 or (len(pre_run) <= 2 and len(post_run) <= 2):
        _base_case()
        return 0

    pre_keys = [normalize(b.canonical) for b in pre_run]
    post_keys = [normalize(b.canonical) for b in post_run]
    sm = SequenceMatcher(a=pre_keys, b=post_keys, autojunk=False)
    opcodes = sm.get_opcodes()

    if len(opcodes) == 1 and opcodes[0][0] == "replace":
        # No progress possible at this depth -> base case, avoids recursing
        # forever on a span with zero internal overlap.
        _base_case()
        return 0

    matched = 0
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            matched += i2 - i1
        elif tag == "delete":
            _handle_delete(pre_run[i1:i2], report)
        elif tag == "insert":
            _handle_insert(post_run[j1:j2], global_j_start + j1, report)
        elif tag == "replace":
            matched += _walk(pre_run[i1:i2], post_run[j1:j2], global_j_start + j1, report, depth + 1)
    return matched


def diff_pair(pre_path: Path, post_path: Path) -> PairReport:
    pre_blocks = select_canonical_blocks(parse_transcript(pre_path))
    post_blocks = select_canonical_blocks(parse_transcript(post_path))

    report = PairReport(
        pair_name=f"{pre_path.name}->{post_path.name}",
        pre_total=len(pre_blocks),
        matched=0,
        retention_ratio=0.0,
    )
    report.matched = _walk(pre_blocks, post_blocks, 0, report)
    report.retention_ratio = round(report.matched / report.pre_total, 3) if report.pre_total else 0.0

    return report


def build_profile(reports: list[PairReport]) -> dict[str, Any]:
    filler_counter: Counter[str] = Counter()
    for r in reports:
        filler_counter.update(r.filler_or_reaction_cuts)

    avg_retention = round(sum(r.retention_ratio for r in reports) / len(reports), 3) if reports else 0.0

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
        "tangent_cuts_for_review": [
            {"pair": r.pair_name, **t} for r in reports for t in r.tangent_cuts
        ],
        "single_line_content_cuts_for_review": [
            {"pair": r.pair_name, "text": t} for r in reports for t in r.content_cuts
        ],
        "rewrites_for_review": [
            {"pair": r.pair_name, **rw} for r in reports for rw in r.rewrites
        ],
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
                "matched_blocks": r.matched,
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
    lines.append("| pair | raw blocks | kept | retention |")
    lines.append("|---|---|---|---|")
    for p in profile["per_pair"]:
        lines.append(f"| {p['pair']} | {p['pre_blocks']} | {p['matched_blocks']} | {p['retention_ratio']} |")

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
