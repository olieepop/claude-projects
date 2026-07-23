---
name: markitdown
description: Convert files (PDF, Word, PowerPoint, Excel, images, audio, HTML, CSV/JSON/XML, ZIP archives, EPub, YouTube URLs, Outlook messages) into clean Markdown using Microsoft's MarkItDown tool. Use this whenever the user wants to turn a document into Markdown or plain text for reading, summarizing, or feeding into an LLM — even if they just say "convert this PDF" or "extract the text from this pptx" without naming MarkItDown directly.
---

# MarkItDown

[MarkItDown](https://github.com/microsoft/markitdown) is Microsoft's Python tool for converting
documents into Markdown. It exists because Markdown is a great intermediate format for LLMs — it's
lightweight, preserves structure (headings, lists, tables, links) far better than plain text, and
most models were trained on huge amounts of it. Reach for MarkItDown any time the task is "get the
content of this file into a form an LLM (or a human) can read," rather than writing one-off parsing
code for PDFs, Office files, etc.

## Setup

Check whether it's already installed before doing anything else:

```bash
markitdown --help
```

If not installed, install only the extras the input actually needs — pulling in `[all]` drags in
heavy dependencies (torch, ffmpeg bindings, etc.) that aren't needed for a single PDF conversion.

```bash
pip install 'markitdown[pdf]'          # just PDF support
pip install 'markitdown[pdf,docx,pptx]' # a few formats
pip install 'markitdown[all]'           # everything, if the file types are unknown/mixed
```

Extras map roughly one-to-one with format families:

| Extra | Adds support for |
|---|---|
| `pdf` | PDF documents |
| `docx` | Word documents |
| `pptx` | PowerPoint presentations |
| `xlsx` | Modern Excel (`.xlsx`) |
| `xls` | Legacy Excel (`.xls`) |
| `outlook` | Outlook `.msg` messages |
| `audio-transcription` | WAV/MP3 speech-to-text |
| `youtube-transcription` | YouTube video transcripts |
| `az-doc-intel` | Azure Document Intelligence backend (scanned/complex PDFs) |
| `az-content-understanding` | Azure Content Understanding backend |

Formats that need no extra: plain HTML, CSV/JSON/XML, ZIP archives (converts each member and
concatenates), EPub, and images (EXIF metadata always; OCR/description needs an LLM client, see
below).

## Converting a file

**CLI — the default choice for a one-off conversion:**

```bash
markitdown path/to/file.pdf -o output.md
# or, to pipe/inspect the Markdown directly:
markitdown path/to/file.pdf
```

**Python API — reach for this inside a script, or when you need to loop over many files, pass
options, or read `result.text_content` directly instead of writing a `.md` file:**

```python
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert("path/to/file.pdf")
print(result.text_content)
```

`convert()` picks the converter based on the file extension/content type. Prefer the narrower
methods below when the input's provenance matters:

- `convert_local(path)` — a file you already trust on disk.
- `convert_stream(stream)` — bytes/file-like object, e.g. an upload — avoids writing untrusted
  input to disk first.
- `convert_response(response)` — pull directly from an HTTP response (e.g. `requests.get(url)`),
  useful for URLs MarkItDown doesn't natively fetch.

Because MarkItDown does file I/O with the privileges of whatever process runs it, treat
conversion of files from an untrusted source (user uploads, scraped URLs) the same as any other
untrusted input — don't convert files from paths or URLs you haven't reasoned about.

## Describing images and scanned content

Plain image conversion only extracts EXIF metadata. To get an actual description of what's in the
image (or better OCR on messy scans), pass an LLM client — this works with any OpenAI-compatible
client, not just OpenAI's models:

```python
from markitdown import MarkItDown
from openai import OpenAI

client = OpenAI()
md = MarkItDown(llm_client=client, llm_model="gpt-4o", llm_prompt="optional custom prompt")
result = md.convert("photo.jpg")
print(result.text_content)
```

## Azure Document Intelligence (better PDF/scan quality)

For scanned or layout-heavy PDFs where the default extraction is messy, route through Azure
Document Intelligence instead — it understands tables and complex layouts much better than plain
text extraction:

```bash
markitdown path/to/file.pdf -o output.md -d -e "<your-doc-intel-endpoint>"
```

```python
md = MarkItDown(docintel_endpoint="<your-doc-intel-endpoint>")
result = md.convert("scanned.pdf")
```

Requires `pip install 'markitdown[az-doc-intel]'` and an Azure Document Intelligence resource —
ask the user for their endpoint rather than guessing at one.

## Plugins

Plugins are disabled by default (`enable_plugins=False`). If the user has a specific plugin
installed (e.g. `markitdown-ocr`), enable it explicitly:

```bash
markitdown --list-plugins          # see what's installed
markitdown --use-plugins file.pdf
```

```python
md = MarkItDown(enable_plugins=True)
```

Don't install a plugin on the user's behalf without asking — check what they already have with
`--list-plugins` first.

## Troubleshooting

- **`ModuleNotFoundError` for a specific format** → the extra for that format isn't installed; add
  it (see the extras table above) rather than falling back to a hand-rolled parser.
- **Garbled/empty output on a scanned PDF** → it's likely image-only with no text layer; suggest
  Azure Document Intelligence (above) or an LLM-based image description pass rather than treating
  it as a MarkItDown bug.
- **Need this in a container** → the repo ships a Dockerfile:
  ```bash
  docker build -t markitdown:latest .
  docker run --rm -i markitdown:latest < input.pdf > output.md
  ```
