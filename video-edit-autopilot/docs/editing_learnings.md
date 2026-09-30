# Editing learnings

Living notes on the gap between "Riverside transcript" (what the Playbook assumes) and
what actually shows up, plus what the CapCut edit does to it. Append a new dated section
per episode — don't rewrite earlier ones, even if a later episode contradicts them.
Patterns that hold across multiple episodes get promoted into
`scripts/prep_transcript.py` as real logic instead of just notes here.

The actual tooling for this lives in `src/` — `edit_style_model.py` and
`rough_cut.py`, ported from [Hao0321/video-autopilot-kit](https://github.com/Hao0321/video-autopilot-kit)
via Olivia's own fork ([creator-voice-autopilot](https://github.com/olieepop/video-autopilot-kit)).
This doc is the narrative writeup; `profiles/edit_style_profile.md` (gitignored,
generated locally by running those scripts) is the authoritative per-pair data —
see §3 below for exact commands.

---

## Ep1 (raw comparison: `ep1_pre.txt` vs `ep1_post.txt`)

**Raw transcript, 3888 cues, 72.2 min.** Final cut, 191 reconstructed cut ranges
totaling 36.1 min — **~50% of raw runtime got cut** (character-level diff via
`rough_cut.py reconstruct`, not a hand count — see §3).

### 1. The raw transcript arrived broken, not just long

The first ~2,199 cues (0:00–1:12 of the raw file) are in Dutch. The show is not in
Dutch — Olivia and Nina talk in Mandarin with English business terms mixed in
(code-switching: "layoff", "director", "who define you is the job define you or you
define yourself"). What's in the Dutch block is phonetically-adjacent gibberish, not a
translation — e.g. post's "雷奥" (a phonetic stand-in for "layoff") shows up in pre as
"Leo". The remaining ~1,689 cues are correctly transcribed Mandarin/English and cover
the same ~72 minutes again from a different starting point.

Best explanation: Riverside transcribes each speaker's local track separately, and one
speaker's track had its language auto-detected wrong — likely due to accent + heavy
code-switching confusing the model — while the other's was transcribed correctly. The
"one transcript file" the Playbook assumes is actually two per-speaker passes
concatenated, and one of them can silently come back in the wrong language with no error,
just fluent-sounding nonsense.

**Consequence for the pipeline:** feeding the raw file straight into `script_01` would
produce titles/show notes/chapters generated from a mix of real content and Dutch
noise, without any signal that half the input is garbage. `script_01` needs a upstream
transcript-quality gate, not just a length limit.

### 2. What actually gets cut in the edit

Comparing where the post transcript starts and ends against the pre transcript's
equivalent content (post has no per-cue timestamp correspondence to pre — the post
transcript is timestamped against the *edited* video, so its clock restarts and
compresses):

- **Opening mic-check/banter is cut entirely.** Pre opens with ~20 seconds of "hoi hoi
  hoi", "who goes first", "is this the intro of the whole show or just this episode" —
  none of it survives. Post starts directly on "大家好我是Lavia" (Olivia's actual
  self-introduction), which is roughly 48 seconds into the raw recording.
- **End-of-recording technical chatter is cut.** Pre's last exchanges are about closing
  the Riverside browser tab / confirming the recording stopped ("我们browser不能关",
  "你停了吗"). None of that is podcast content and none of it survives.
- **Mid-episode filler and tangents are trimmed throughout**, not just at the edges —
  the ~50% overall cut is too large to be explained by the intro/outro alone. The
  longest single cut is 342s (5.7 min) at the 62-minute mark, a tangent about feeling
  stuck on direction — see `profiles/edit_style_profile.md`'s "Verified real cuts"
  section for the full list of 191 cut ranges.
- Post's very last two cues are out of chronological order (a "拜拜" sign-off at 34:03
  immediately followed by a cue timestamped 19:41). That's consistent with a pickup line
  or alternate take spliced in near the very end of the CapCut edit — worth knowing so a
  chapter-detection script doesn't assume post-edit SRT timestamps are strictly
  monotonic.

### 3. What this means for the scripts

- `script_01_text_outputs.py` should run against the **post-edit transcript** (the
  transcript of the CapCut export), not the raw Riverside download — the raw one is
  ~2x longer, partly in the wrong language, and includes recording-logistics chatter
  that would leak into auto-generated show notes/chapters if not filtered.
- `scripts/prep_transcript.py` catches the specific failure mode above before anything
  downstream runs: flags any stretch of cues with near-zero CJK character density in a
  transcript that's supposed to be Mandarin/English, so a mis-detected-language block
  gets caught instead of silently producing fluent-looking nonsense.
- `src/edit_style_model.py select_canonical_blocks` handles the same problem a
  different way — it auto-detects a language-segmented file and drops the
  non-dominant-language blocks before diffing, so the Dutch block doesn't corrupt the
  learned profile. It doesn't warn you it did this, though, which is why
  `prep_transcript.py` is worth keeping as an explicit check.
- `src/edit_style_model.py`'s block-level `learn` command undercounts retention badly
  on ep1 (reports 19.7%, not the real ~50%) because the raw and final transcripts chunk
  sentences differently — a documented limitation. `src/rough_cut.py reconstruct` (a
  character-level diff) doesn't have this problem; its output is what's actually
  trustworthy for the real cut ranges, merged into `edit_style_profile.json`'s
  `verified_real_cuts_ep1` field so future tangent judgment has ground truth to
  calibrate against.

### Regenerating this for a new episode

```bash
python src/edit_style_model.py learn \
  --pair episodes/ep1/ep1_pre.srt=episodes/ep1/ep1_post.srt \
  --pair episodes/ep2/ep2_pre.srt=episodes/ep2/ep2_post.srt \
  --out profiles/edit_style_profile
python src/rough_cut.py reconstruct \
  --pre episodes/ep2/ep2_pre.srt --post episodes/ep2/ep2_post.srt \
  --out profiles/ep2_cuts.json
```
Both write to `profiles/`, which is gitignored — this is derived from raw, unedited
personal speech and stays local, never in the repo.

### 4. Ep1 is a process outlier, not just a transcript-quality one

Confirmed against Drive (see `docs/outline_location.md`): every episode from ep2
onward has a pre-recording outline doc (planned topics, timed segments, a stated
episode purpose). **Ep1 has none.** That's very likely a real contributor to why
ep1 needed such heavy tangent-cutting — there was no agreed structure keeping the
raw conversation anchored, so it ran long and wandered further than a scripted
episode would.

Practical consequence: ep1's biggest single cut (342s, a tangent about feeling
stuck on direction) is marked `"generalizable": false` in
`profiles/edit_style_profile.json`'s `verified_real_cuts_ep1` — it's this
conversation's own judgment call, not a repeatable editing rule, and with no
outline to check it against there's no way to tell whether it was "off the
planned topic" (ep1 didn't have one) or just a natural tangent. The smaller,
structural cuts (opening banter, recording logistics) are kept as generalizable
patterns; see `profiles/edit_style_profile.md`'s "Recognizable editing patterns"
section.

Once an outlined episode (ep2+) has a real pre/post transcript pair, its cuts are
a much better source for calibrating tangent judgment specifically — diff against
the outline's planned segments, not just "what got cut" in isolation.
