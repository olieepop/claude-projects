"""
Sanity-checks a raw Riverside transcript before it goes into script_01.

Why this exists: ep1's raw transcript came back as two per-speaker passes
concatenated into one file, and one of the two had its language mis-detected —
it transcribed as fluent-sounding Dutch instead of the actual Mandarin/English
speech, with no error or low-confidence marker. See docs/editing_learnings.md
for the full writeup. Feeding that straight into script_01 would silently
produce titles/show notes generated partly from gibberish.

This script parses an .srt/.vtt transcript and flags any stretch of cues whose
CJK character density is far below the rest of the file — the signature of a
mis-detected-language block for a Mandarin/English show. It doesn't fix the
transcript (that still needs a manual re-run through Riverside/Whisper with
the language forced); it just stops a broken input from reaching script_01
unnoticed.

Usage:
    python scripts/prep_transcript.py path/to/riverside_transcript.srt
"""

import re
import sys
from dataclasses import dataclass

CJK_RE = re.compile(r"[一-鿿]")
CUE_TIME_RE = re.compile(
    r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})"
)

# A rolling window this many cues wide is checked for CJK density. Tune down
# for shorter clips.
WINDOW_SIZE = 50

# Below this fraction of "has at least one CJK character" cues in a window,
# flag it as a likely mis-transcribed block. This show is Mandarin-led with
# English code-switching, so even a heavily-English stretch should still have
# *some* Chinese in most cues; a window near zero is the tell.
DENSITY_FLOOR = 0.15


@dataclass
class Cue:
    index: int
    start: str
    end: str
    text: str


def parse_srt(path: str) -> list[Cue]:
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    cues: list[Cue] = []
    blocks = re.split(r"\n\s*\n", raw.strip())
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip() != ""]
        if len(lines) < 2:
            continue
        time_line_idx = next(
            (i for i, ln in enumerate(lines) if CUE_TIME_RE.search(ln)), None
        )
        if time_line_idx is None:
            continue
        m = CUE_TIME_RE.search(lines[time_line_idx])
        assert m is not None
        try:
            index = int(lines[0]) if time_line_idx > 0 else len(cues) + 1
        except ValueError:
            index = len(cues) + 1
        text = " ".join(lines[time_line_idx + 1 :]).strip()
        cues.append(Cue(index=index, start=m.group(1), end=m.group(2), text=text))
    return cues


def find_suspect_windows(cues: list[Cue]) -> list[tuple[int, int, float]]:
    """Returns (start_cue_index, end_cue_index, cjk_density) for windows below the floor."""
    suspects = []
    for start in range(0, len(cues), WINDOW_SIZE):
        window = cues[start : start + WINDOW_SIZE]
        if not window:
            continue
        with_cjk = sum(1 for c in window if CJK_RE.search(c.text))
        density = with_cjk / len(window)
        if density < DENSITY_FLOOR:
            suspects.append((window[0].index, window[-1].index, density))
    return suspects


def merge_windows(suspects: list[tuple[int, int, float]]) -> list[tuple[int, int]]:
    """Collapses adjacent flagged windows into contiguous ranges for a readable report."""
    if not suspects:
        return []
    merged = [(suspects[0][0], suspects[0][1])]
    for start, end, _ in suspects[1:]:
        if start <= merged[-1][1] + WINDOW_SIZE:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    path = sys.argv[1]
    cues = parse_srt(path)
    if not cues:
        print(f"No cues parsed from {path} — check the file format.")
        sys.exit(1)

    overall_density = sum(1 for c in cues if CJK_RE.search(c.text)) / len(cues)
    print(f"{path}: {len(cues)} cues, overall CJK-cue density {overall_density:.0%}")

    suspects = find_suspect_windows(cues)
    ranges = merge_windows(suspects)
    if not ranges:
        print("No suspect low-CJK blocks found.")
        return

    print(
        f"\n{len(ranges)} suspect block(s) found — likely mis-detected language, "
        "not real English/code-switching:"
    )
    for start_idx, end_idx in ranges:
        start_cue = next(c for c in cues if c.index == start_idx)
        end_cue = next(c for c in cues if c.index == end_idx)
        print(
            f"  cues {start_idx}-{end_idx} "
            f"({start_cue.start} -> {end_cue.end}): "
            f'"{start_cue.text[:60]}"'
        )
    print(
        "\nDo not feed this file into script_01 as-is — re-run the affected "
        "range through transcription with the language forced, then re-check."
    )


if __name__ == "__main__":
    main()
