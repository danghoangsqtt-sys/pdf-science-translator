---
name: pdf-translate
description: Translate local PDFs, including safe prose on image-only scans, into Vietnamese or another supported Latin-script language while preserving layout, formulas, tables, and figures. Use for PDF translation, OCR-assisted scan translation, batch translation, terminology-sensitive handoff translation, or diagnosing incomplete output. Do not use for targets requiring CJK, right-to-left, or complex-script shaping.
license: AGPL-3.0-only
---

# PDF Translate

Translate a PDF with the bundled Code4Life engine. Keep the source file unchanged and produce a separate PDF with the same page structure.

When this skill runs inside the repository, first read
[`agent-knowledge/index.md`](agent-knowledge/index.md). For preservation or
layout work, load its PDF engine, regression, and validation routes. These are
the shared project instructions for Codex and Claude; do not duplicate them in
this entrypoint.

## Resolve the skill root

This skill may be installed globally while the user's files live elsewhere. Resolve the absolute directory containing this `SKILL.md` before running anything. Call its scripts and dependency files by absolute path; do not assume the current working directory is the skill directory.

Use the interpreter inside `<skill-root>/.venv`:

- Windows: `<skill-root>\.venv\Scripts\python.exe`
- macOS/Linux: `<skill-root>/.venv/bin/python`

## Choose a mode

| Mode | Translator | Use when |
| --- | --- | --- |
| Ollama (default) | `translategemma:12b` on the local machine | Private documents, no account, no network |
| Azure | Azure Translator v3 with the user's key | The user has a key and wants the official service |
| Google | `translate.google.com` | Fallback when neither is available |
| Handoff | The active agent | Terminology, context, or translation quality matters |

Default to Ollama. The runner checks the server and model before reading any
page and says how to fix it (`ollama pull translategemma:12b`); offer
`--model translategemma:4b` on a weak machine. Use Google only as a fallback:
its free endpoint blocks an IP that sends it a whole document, and the runner
then stops with a Vietnamese message instead of retrying. Offer handoff when
the user asks for higher quality or provides a short technical document.

Report the translated share the runner prints (`Translated 34/43 segments
(79%)`) and every kept-source reason; a run with nothing translated is an
error, never a delivered file.

## Boundaries

- Use the bundled `pdf2zh/` core. Never substitute the PyPI `pdf2zh` package; the runner checks version `1.9.11` and preservation ruleset `code4life-preservation-v1` and refuses an external core.
- Google and Azure modes send extracted document text to those services. Tell the user before processing sensitive material and obtain explicit confirmation unless their request already authorizes that disclosure. Ollama and handoff modes keep the text on the machine.
- Azure reads `AZURE_TRANSLATOR_KEY`/`AZURE_TRANSLATOR_REGION` or the per-user `engines.json`; never write a key into the repository or a command shown to the user.
- Supported targets are the Latin-script codes enforced by `scripts/translate_pdf.py`. CJK, right-to-left, Thai, Devanagari, and other complex-shaping targets are rejected because the bundled font and layout engine cannot render them reliably.
- OCR is opt-in with `--ocr standard|enhanced`. It fails closed on unsafe tables,
  formulas, figures, code and ambiguous reading order; report every preserved
  region as partial instead of claiming the whole scan was translated.
- Text inside detected tables, figures, contents pages, indexes, symbol lists, or references may intentionally remain in the source language. Report material untranslated regions as partial translation.
- Preserve the source. Write results to a separate output directory. Do not pass `--overwrite` without explicit replacement authorization.

Read [the preservation contract](references/preservation-rules.md) before changing layout behavior, diagnosing preserved pages, or investigating untranslated regions.

## Set up the runtime

Use Python 3.11 or 3.12. Create `<skill-root>/.venv` and install `<skill-root>/requirements.txt` if the environment is absent or stale. Keep this environment separate from the user's project.

The source distribution downloads layout and font assets on its first translation, so the first run needs network access and takes longer. The packaged Windows app already contains these assets.

Windows:

```powershell
python -m venv "<skill-root>\.venv"
& "<skill-root>\.venv\Scripts\python.exe" -m pip install -r "<skill-root>\requirements.txt"
```

macOS/Linux:

```bash
python3 -m venv "<skill-root>/.venv"
"<skill-root>/.venv/bin/python" -m pip install -r "<skill-root>/requirements.txt"
```

Shared runner options include `--target-language` (default `vi`), `--source-language auto`, one-based `--pages 1,3-5`, `--threads 1..8` (default `2` for Ollama, `4` otherwise), `--engine ollama|azure|google|handoff`, `--model` (Ollama only), `--ignore-cache`, and `--overwrite`.

## Ollama, Azure or Google mode

Add `--engine azure` or `--engine google` to choose those engines; Ollama needs
no flag. Run one command per file. Use absolute paths for the input and output directory.

Windows:

```powershell
& "<skill-root>\.venv\Scripts\python.exe" "<skill-root>\scripts\translate_pdf.py" "<input.pdf>" --output-dir "<output-dir>"
```

macOS/Linux:

```bash
"<skill-root>/.venv/bin/python" "<skill-root>/scripts/translate_pdf.py" "<input.pdf>" --output-dir "<output-dir>"
```

For a batch, process files individually and report progress. A failure on one file must not stop the remaining files; collect and report all failures at the end.

## Handoff mode

Handoff extracts translatable segments to JSONL, lets the active agent translate them, then rebuilds the PDF. Warn about token and time cost before starting a large document. For long documents, suggest a representative sample such as `--pages 1-5` first.

### 1. Extract

An output directory is not required during extraction because the pass-one PDF is discarded.

```text
<python> <skill-root>/scripts/translate_pdf.py <input.pdf> --engine handoff --emit-segments <segments.jsonl>
```

### 2. Translate

Read `segments.jsonl` in manageable batches. Write one JSON object per line to `translations.jsonl`:

```json
{"src":"exact source text","dst":"translated text"}
```

Copy each `src` value exactly. Preserve URLs, paths, identifiers, citation markers, and numbers.

Formula and code placeholders such as `<b0></b0>` are immutable. Every opening and closing tag must retain the same identifier, count, and order as the source. The loader rejects a record whose placeholders differ, leaving that segment untranslated.

Inline emphasis markers are immutable as balanced pairs: `<s1>...</s1>` is
bold, `<s2>...</s2>` is italic, and `<s3>...</s3>` is bold italic. Complete
style pairs may move with the translated phrase, but none may be dropped,
duplicated, or cross-nested. Invalid style markup leaves the segment
untranslated instead of silently losing emphasis.

### 3. Rebuild

```text
<python> <skill-root>/scripts/translate_pdf.py <input.pdf> --engine handoff --segments <translations.jsonl> --output-dir <output-dir> --emit-segments <still-missing.jsonl>
```

The command prints the remaining untranslated segment count. If it is nonzero, translate `still-missing.jsonl`, append valid records to `translations.jsonl`, and rebuild again. Stop only at zero or when a segment cannot be translated safely; then report the exact remaining limitation.

Extraction and rebuild each run the layout pass, so handoff uses roughly twice the local PDF processing of the other modes in addition to the agent's translation work.

## Verify before delivery

1. Confirm the output exists and the source still exists unchanged.
2. Confirm source and output page counts match.
3. Extract text page by page and check for substantial untranslated passages, missing formulas, damaged URLs, or lost identifiers.
4. When page rendering or image inspection is available, render every output page and inspect for blank pages, missing glyphs, clipping, overlap, and displaced tables or figures.
5. If full visual inspection is unavailable, say which checks were completed. Do not present a partially verified or partially translated file as fully complete.
