# MarkItDown Skill

A Claude Code / Claude Cowork skill that teaches Claude how to use
[Microsoft's MarkItDown](https://github.com/microsoft/markitdown) to convert files into clean
Markdown — the format LLMs read best.

## What it does

Wires Claude up to convert PDFs, Word/PowerPoint/Excel files, images, audio, HTML, CSV/JSON/XML,
ZIP archives, EPubs, Outlook messages, and YouTube URLs into Markdown, via either the `markitdown`
CLI or its Python API. It covers:

- Installing only the pip extras a given conversion actually needs (`markitdown[pdf]`,
  `markitdown[docx,pptx]`, `markitdown[all]`, etc.)
- CLI (`markitdown file.pdf -o output.md`) vs. Python API (`MarkItDown().convert(...)`), and when
  to reach for each
- The narrower `convert_local` / `convert_stream` / `convert_response` methods for handling
  untrusted input safely
- LLM-based image description via an OpenAI-compatible `llm_client`
- Azure Document Intelligence integration for higher-quality scanned/complex PDF extraction
- The plugin system (`--list-plugins`, `--use-plugins`, `enable_plugins`)
- Common failure modes (missing extras, image-only PDFs) and how to resolve them

## Setup

No connectors or credentials needed to get started. The skill installs `markitdown` (with the
right extras) on demand via `pip`. Azure Document Intelligence / Content Understanding features
additionally require an Azure resource endpoint, which the skill will ask the user for rather than
assume.

## Using it

Just ask Claude to convert a file — e.g. "convert this PDF to markdown" or "extract the text from
this pptx so I can summarize it." Claude will pick the CLI or Python API as appropriate, install
whatever extras the file type needs, and hand back the resulting Markdown.

## License

MIT
