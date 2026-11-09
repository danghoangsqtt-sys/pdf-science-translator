---
name: pdf-translate
description: Translate or diagnose local text-based PDFs in this repository while preserving layout, formulas, tables, figures, styles, rotation, and technical glyphs. Use for PDF translation, incomplete output, visual regressions, or preservation fixes; not for OCR-only scans or complex-script targets.
---

# PDF Translate Project Skill

This is the Claude Code adapter for the canonical cross-agent skill.

Before acting:

1. Read `../../../SKILL.md` completely and follow its workflow and boundaries.
2. Read `../../../agent-knowledge/index.md`, then its routed PDF engine,
   regression, and validation files relevant to the request.
3. Resolve commands from the repository root containing `backend/pdf2zh/` and
   `backend/scripts/translate_pdf.py`, not from this adapter directory.

On macOS use `.venv/bin/python`; on Windows use `.venv\Scripts\python.exe`.
The preservation behavior and tests are shared across platforms. Keep the source unchanged, validate rendered
output, and report partial fallbacks honestly.
