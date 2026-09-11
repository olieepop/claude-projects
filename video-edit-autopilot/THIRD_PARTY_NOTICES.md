# Third-party notices

Most of `src/` is ported, unmodified, from [Hao0321/video-autopilot-kit](https://github.com/Hao0321/video-autopilot-kit)
by way of Olivia's fork, [olieepop/video-autopilot-kit](https://github.com/olieepop/video-autopilot-kit),
under the MIT License:

- `src/rough_cut.py`
- `src/edit_style_model.py`
- `src/delivery_media_ops.py`
- `src/media_delivery_qa.py`
- `src/filter_runtime.py`, `src/filter_primitives.py`, `src/filter_renderers.py`, `src/filter_materials.py`
- `src/platform_compat.py`
- `templates/voice_profile.template.md`, `templates/style_profile.template.md`, `templates/brand_profile.template.md`
- `knowledge/runtime/filter_library.json`, `knowledge/runtime/filter_materials.json`

`src/dual_subtitle.py` and `templates/edit_style_profile.template.md` are ported from
[olieepop/podcast-audio-autopilot-kit](https://github.com/olieepop/podcast-audio-autopilot-kit),
itself a downstream copy of the same fork with the CapCut-review SRT path added — see that
repo's own `THIRD_PARTY_NOTICES.md` for the original chain.

`scripts/script_01_text_outputs.py`, `scripts/script_02_buzzsprout_upload.py`,
`scripts/script_03_youtube_prep.py`, `scripts/prep_transcript.py`, and
`docs/production_playbook.md` / `docs/editing_learnings.md` are Olivia's own work, carried
over unmodified from `podcast-audio-autopilot-kit`.

```
MIT License

Copyright (c) 2026 Hao0321 Studio

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

`src/brand_insert.py`, `src/audio_export.py`, `src/final_transcript.py`, and `src/pipeline.py`
are new — written to close the gap between what the two source kits already did and the
raw-video-in/four-deliverables-out process this repo targets. All other files are original.
