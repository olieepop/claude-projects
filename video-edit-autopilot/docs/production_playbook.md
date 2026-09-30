# The Long Way Here — Production Playbook

Mirror of the working doc in Drive ("The Long Way Here — Production Playbook.pdf",
v1.0, June 2026). Update the Drive doc first when a real process change is made, then
sync this copy — this file exists so the scripts' input/output contracts are versioned
next to the code, not so it becomes a second source of truth.

## At a glance

- **Cadence:** bi-weekly, 2 episodes/month during the 3-month trial
- **Recording:** Riverside.fm free tier (2hr/month cap, 720p, separate per-speaker tracks)
- **Production owner:** Olivia, through the trial
- **Platforms:** YouTube + podcast (Spotify/Apple via Buzzsprout)

## Episode pipeline

**Phase A — Pre-production.** Lead host (rotates per episode) drafts a 1-page outline
(topic, 3–5 talking points, CTA) about a week out; non-lead reviews.

**Phase B — Record.** Riverside session, both join via browser. Records each speaker on
a separate local track. Target 30–45 min raw.

**Phase C — Audio & text processing.**
1. Download Olivia's and Nina's tracks (audio + video) plus the Riverside-generated
   transcript.
2. Audio cleanup: run both tracks through ElevenLabs Pro Speech Enhancement.
3. **Script 1** (`script_01_text_outputs.py`): transcript in, all written content out.

**Phase D — Video editing.** CapCut, using saved templates: sync both tracks (cleaned
audio, not raw Riverside audio) → trim dead air + filler → 5s branded intro → lower
thirds → branded outro with CTA → export.

**Phase E — Publish.** Export full video (1080p MP4) and audio-only (MP3, 192kbps) from
the same CapCut project. **Script 2** drafts the Buzzsprout upload; **Script 3** preps
the YouTube upload checklist. Both platform uploads are reviewed/published by a human.

## Claude Code automation — script contracts

### `script_01_text_outputs.py` — run after Phase C step 2

- **Input:** Riverside transcript (`.txt` or `.vtt`), `episode_number`, optional
  `guest_name`
- **Does:** sends the transcript to the Claude API with a structured prompt requesting:
  1. 3 episode title options (punchy, specific, audience-aware)
  2. Show notes, ~200 words (guest names, topics covered, CTA)
  3. YouTube description with timestamped chapter markers auto-detected from the
     transcript
  4. Podcast episode description for Buzzsprout, ~100 words
  5. 3 pull quotes
- **Output:** single markdown file `episode_[date]_content.md`, saved to the Drive
  episode folder

### `script_02_buzzsprout_upload.py` — run after Phase E export

- **Input:** episode MP3, `episode_[date]_content.md`
- **Does:** authenticates to the Buzzsprout REST API (API key in `.env`), creates a
  draft episode — uploads audio, sets title/description from the content file, sets
  chapter markers if present. Leaves it as **Draft**; a human reviews and publishes.
- **Output:** Buzzsprout episode URL

### `script_03_youtube_prep.py` — run after Phase E export; upload itself stays manual

- **Input:** `episode_[date]_content.md`
- **Does:** validates chapter format (YouTube requires `HH:MM:SS`/`MM:SS` at line start),
  generates a thumbnail brief (text overlay, episode number, topic keyword)
- **Output:** `youtube_upload_checklist.md` — title, description, tags, thumbnail brief,
  target playlist, all copy-paste ready

**Phase 2 goal (month 2+):** chain scripts 1→2→3 into one command triggered by dropping
transcript + audio into a watched folder; add YouTube Data API v3 upload once OAuth is
set up.

## Tools ($0 new cost)

Riverside.fm (free tier) · ElevenLabs Pro (Olivia's account) · CapCut (Olivia's account)
· Claude + Claude Code · Buzzsprout (both admins) · YouTube Studio (manual upload)
