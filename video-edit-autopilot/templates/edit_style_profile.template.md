# Edit Style Profile — how you *cut*, not how you write

> Companion to [`voice_profile.template.md`](voice_profile.template.md) and
> [`style_profile.template.md`](style_profile.template.md), which cover how you
> *write*. This one covers how you *edit*: what actually gets cut between a
> raw recording and the version you publish.
>
> Unlike the other two templates, you don't fill this one by hand — you
> generate it from your own back catalog with
> [`../src/edit_style_model.py`](../src/edit_style_model.py), then review it.

## §0 What you need

At least one pair of transcripts per episode/video you want to learn from:

- **Raw**: the transcript of the unedited recording (ASR output is fine)
- **Final**: the transcript of the version you actually published

Both in SRT-like blocks (`index` / `HH:MM:SS,mmm --> HH:MM:SS,mmm` / text
line(s) / blank line). Bilingual-per-block and language-segmented-per-block
transcripts are both handled — the tool auto-detects which.

More pairs = a more reliable signal, same as the rest of this kit's
"audited from your own transcripts" philosophy. One pair gets you a rough
draft; three to five gets you something you can actually trust.

## §1 Generate it

```bash
python src/edit_style_model.py learn \
  --pair raw_ep01.txt=final_ep01.txt \
  --pair raw_ep02.txt=final_ep02.txt \
  --out profiles/edit_style_profile
```

Writes `profiles/edit_style_profile.json` (machine-readable) and
`profiles/edit_style_profile.md` (the review checklist — read this one).

## §2 Review it (don't skip this)

The output is candidates, not conclusions. For each section:

- **Frequent filler/reaction cuts** — keep the ones that are really your
  verbal tics; some short lines get flagged here that are actually content
  (short answers, agreement that mattered). Delete the ones that aren't real.
- **Tangent cuts** — label each one (e.g. "off-topic riff," "tech
  troubleshooting aside," "repeated explanation"). This is the most useful
  section: it's your show's actual "what doesn't survive the edit" pattern.
- **Rewrites/corrections** — mostly ASR fixes and homophone corrections.
  Skim for anything that looks like an actual content change, not a typo fix.
- **Added hooks** — cold-open lines that exist in the final cut but not the
  raw recording. If you write these fresh per episode, this is your evidence
  for what a hook in your voice actually sounds like.
- **Retention ratio** — treat with caution if your raw and final transcripts
  resegment sentences differently (different block boundaries for the same
  words); the ratio undercounts survival in that case. The tangent-cut list
  is the more reliable signal either way.

## §3 What this is for

A brief, not an executor. There's no cutting engine wired to this in the
public kit (see the note at the top of the main README about Editkin v4).
Hand the reviewed profile to whoever/whatever actually cuts your footage —
yourself, a human editor, an assistant, or a future automation step — the
same way `profiles/voice.md` is a brief for whoever writes your scripts.
