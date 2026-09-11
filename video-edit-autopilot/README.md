# video-edit-autopilot

One pipeline, merged from two repos that had already started overlapping: raw video in →
your editing style applied, brand material added, transitions where the footage earns them →
edited video + edited audio + captions + transcript out.

## Why this exists

You had two separate kits doing adjacent things, and they'd already started copying files
into each other:

- **`podcast-audio-autopilot-kit`** — the real, working publish pipeline for *The Long Way
  Here*: transcript → titles/show notes/YouTube description → Buzzsprout draft → YouTube
  checklist. It had *also* copied five files straight out of `video-autopilot-kit`
  (`edit_style_model.py`, `rough_cut.py`, `dual_subtitle.py`, `delivery_media_ops.py`,
  `media_delivery_qa.py`) because that's where the only working style-learning and cut-list
  code lived.
- **`video-autopilot-kit`** — your fork of Hao0321's general-purpose framework. Large (200+
  files): long-form/Shorts/interview pipelines, a filter library, tracked graphics, a drama
  pipeline, a silent-vlog maker. Most of its most elaborate machinery (the design system,
  templated motion graphics, the full plan→audit→apply→render DAG) is gated behind
  **Editkin v4**, a private client/server that isn't in the public fork — so those parts
  don't run for you today.

Confirmed by diff: `rough_cut.py`, `edit_style_model.py`, `delivery_media_ops.py`,
`media_delivery_qa.py` were byte-identical copies. `dual_subtitle.py` had already **drifted**
— the podcast repo's copy added a CapCut-review `.srt` export path that the upstream fork
doesn't have. That's exactly the kind of silent fork-drift that gets worse every episode if
left alone (next update to one copy, the other quietly falls behind).

## What's actually usable without Editkin

This matters because it changes what "auto-editing" can mean right now. Checked directly,
not assumed from the README's framing:

| Tool | Needs Editkin? | What it does |
|---|---|---|
| `rough_cut.py propose / reconstruct / merge / apply` | **No** | Derives and *executes* a cut list with real `ffmpeg` calls — confirmed by reading the code, not just the CLI help |
| `edit_style_model.py learn` | No | Learns your cut patterns from raw/published transcript pairs — pure Python |
| `filter_runtime.py apply / transition` | No | Grades, transitions, subject filters — plain `ffmpeg`/OpenCV, no external dependency |
| `dual_subtitle.py build / burn` | No | Bilingual captions, SRT (CapCut-review) or hard-burned | 
| `media_delivery_qa.py` / `delivery_media_ops.py` | No | Dead-air/flash/AV-sync/caption-sync QA | 
| Design system, motion graphics, tracked-graphics templates, the full plan/audit/render DAG | **Yes** | Not available in this fork — out of scope here |

So the gap between what you have and "raw video → my style → branded, captioned, delivered"
isn't Editkin. It's four small pieces neither kit built: **stitching in brand material**,
**an audio-only master**, **a transcript that matches the edited output** (not the raw
footage), and **one command that produces all three from a reviewed cut list**. That's the
net-new code here — everything else is vendored, unmodified, from tools that already work.

## The pipeline

```
raw video + raw transcript
  -> edit_style_model.py learn         (once you have raw/published pairs — builds your style profile)
  -> rough_cut.py propose              (mechanical: dead-air + learned-filler candidates)
  -> [LLM tangent judgment]            (see rough_cut.py's own TANGENT_JUDGMENT_RECIPE docstring)
  -> rough_cut.py merge                (combine the two candidate lists)
  -> *** human reviews cuts.json ***   (delete anything wrong — both kits are explicit: never
                                         apply a derived cut list unreviewed)
  -> rough_cut.py apply                (video + reviewed cuts.json -> rough_cut.mp4)
  -> [filter_runtime.py apply/transition]  (grade + transitions, only where evidenced/motivated)
  -> pipeline.py finish                (NEW — the orchestrator this repo adds):
       -> brand_insert.py    (+ intro/outro, normalizes mismatched res/fps/codec)
       -> dual_subtitle.py   (captions.srt for CapCut review, or --burn to hard-burn)
       -> audio_export.py    (clean MP3 master)
       -> final_transcript.py (raw transcript, cut ranges removed, timestamps remapped
                                to match the edited video)
  -> [CapCut, if not burning captions]  review/adjust captions + timing, export final
  -> scripts/script_01_text_outputs.py     (titles, show notes, YT description, pull quotes)
  -> scripts/script_02_buzzsprout_upload.py (podcast draft)
  -> scripts/script_03_youtube_prep.py      (YouTube upload checklist)
```

Four deliverables land in one `--out-dir`: `video.mp4` (+ `video_captioned.mp4` if `--burn`),
`audio.mp3`, `captions.srt`, `transcript.srt`.

**Deliberately not automated further:** cut-list review and (by default) caption review stay
manual. Both source kits say this explicitly and repeatedly — a derived list that removes
content from your only footage is exactly the kind of action where "looks right" isn't good
enough to skip a human look. `pipeline.py` picks up *after* that review, not instead of it.

## Quickstart

```bash
pip install -r requirements.txt
pip install -r requirements-media.txt   # Pillow, numpy, opencv — needed by filter_runtime.py
cp .env.example .env                    # ANTHROPIC_API_KEY, BUZZSPROUT_API_KEY, BUZZSPROUT_PODCAST_ID
```

Requires `ffmpeg`/`ffprobe` on PATH (checked in this environment: not preinstalled — install
via your package manager, e.g. `apt install ffmpeg` / `brew install ffmpeg`).

```bash
# 1. build your style profile (once you have raw+published transcript pairs)
python src/edit_style_model.py learn --pair raw1.srt=final1.srt --pair raw2.srt=final2.srt \
    --out profiles/edit_style_profile

# 2. propose cuts for a new episode, review cuts.json by hand, then apply
python src/rough_cut.py propose --transcript raw.srt --video raw.mp4 \
    --profile profiles/edit_style_profile.json --out cuts.json
#   <<< open cuts.json, delete anything you disagree with >>>
python src/rough_cut.py apply --video raw.mp4 --cuts cuts.json --out rough_cut.mp4

# 3. brand + audio + transcript + captions in one step
python src/pipeline.py finish \
    --video rough_cut.mp4 --cuts cuts.json --raw-transcript raw.srt \
    --intro assets/intro.mp4 --outro assets/outro.mp4 \
    --captions captions.json --out-dir out/ep8/

# 4. publish-side text (existing podcast pipeline, unchanged)
python scripts/script_01_text_outputs.py ...
python scripts/script_02_buzzsprout_upload.py ...
python scripts/script_03_youtube_prep.py ...
```

Smoke-tested end to end against synthetic footage (10s test clip, one cut, mismatched
intro/outro resolutions and frame rates to prove the brand-insert normalization actually
works) before this was committed — see the diff for the exact commands if you want to rerun
it against your own short clip first.

## Structure

- `src/rough_cut.py`, `edit_style_model.py`, `delivery_media_ops.py`, `media_delivery_qa.py`,
  `filter_runtime.py` (+ `filter_primitives.py`/`filter_renderers.py`/`filter_materials.py`),
  `platform_compat.py` — vendored unmodified from `video-autopilot-kit`. Attribution in
  `THIRD_PARTY_NOTICES.md`.
- `src/dual_subtitle.py` — vendored from `podcast-audio-autopilot-kit`'s already-diverged
  (better) copy.
- `src/brand_insert.py`, `audio_export.py`, `final_transcript.py`, `pipeline.py` — **new**,
  written for this merge to close the gap described above.
- `scripts/` — the podcast publish pipeline, unchanged from `podcast-audio-autopilot-kit`.
- `templates/` — voice/style/brand/edit-style profile templates (fill in, save as
  `profiles/*.md`, gitignored).
- `docs/production_playbook.md`, `docs/editing_learnings.md` — carried over as reference;
  update the Drive original first per that doc's own note.
- `knowledge/runtime/` — filter library + material definitions `filter_runtime.py` reads.
- `profiles/`, `out/`, `assets/` — gitignored. Your style profile, pipeline output, and
  brand video files never belong in this repo.

## What didn't get merged, and why

- **Everything Editkin-gated in `video-autopilot-kit`** (design system, motion templates,
  tracked graphics, the full DAG controller, Shorts/drama/silent-vlog pipelines) — stayed in
  that repo. It doesn't run without a tool you don't have, and pulling 150+ more files in on
  the chance you get Editkin access later isn't worth the maintenance surface now. If that
  changes, vendor the specific pipeline you need the same way this repo vendored `rough_cut`.
- **`interview_autopilot.py` / `interview_gate.py`** — genuinely relevant (two-host podcast
  format) but not pulled in yet since nothing in the current process calls it. Worth adding
  once you actually use the guest-invite/prep-kit workflow.
- **Upstream sync** — these are now independent copies again, same problem that produced the
  original drift. If `video-autopilot-kit` gets a real bugfix to `rough_cut.py`, it has to be
  applied here by hand (or vice versa for `dual_subtitle.py`'s CapCut-SRT addition, which
  upstream doesn't have). No automated sync exists — a `diff` against both source repos
  before a big edit is the cheapest guard until this is worth scripting.

## Environment (checked at last install)

- Python 3.11.15
- `ffmpeg`/`ffprobe` 6.1.1 — not preinstalled, needed on PATH
- Pillow 11.3.0, numpy 2.0.2, opencv-contrib-python-headless 4.12.0 — needed by
  `filter_runtime.py`'s tracked-graphics/subject-matte code (this is the "b-roll widget":
  OpenCV, not a separate application)
- `anthropic`, `requests` — needed by `scripts/script_01_text_outputs.py` /
  `script_02_buzzsprout_upload.py`
