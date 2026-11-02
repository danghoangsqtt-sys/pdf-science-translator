# Validation and PDF QA

## Automated Gate

For offline Windows also run `tests/test_offline.py`, the profile API tests and
`npm run test:viewer`. The Chromium harness must use the production sandbox
preload with a non-default API port; testing only 8089 missed a packaged CSP bug.
Verify preparing/missing resources block translation and never silently downgrade.
Real jobs must use the owned worker and copied data, not the developer's separate
service. Check all three profiles on the same source and record partial output.
Load both OCR modes with the packaged Python and outbound guard active.
Record packaged startup, actual UI translation, public errors, and network observations.
A loopback-only TCP snapshot is evidence, not a substitute for clean-machine/network
isolation acceptance. Do not claim clean Windows qualification without performing it.

Run from the repository root with the platform virtual environment:

```text
python -m unittest discover -s tests -v
python -m pip check
python -m ruff check pdf2zh scripts app tests webui/backend --select E9,F63,F7,F82
```

With `webui/frontend/node_modules` present, `npx tsc -b` in `webui/frontend`
must pass. Backend tests skip themselves when FastAPI is not installed.

`git diff --check` must be clean. For desktop changes, start the app with
`npm run dev` in `webui/frontend` and translate one document end to end.

The Ollama unit module blocks real HTTP at `requests.Session.request`; model
status, replies and retry delays must be mocked. Native smoke checks still load
the real layout/OCR runtime and require the bundled assets. For the Electron
PDF panes, run `npm run test:viewer` in `webui/frontend`: it checks gutter
geometry and native Chromium interactions without a real translation service.

## Engine Gate

Engine tests mock HTTP; never call Ollama, Azure or Google from unit tests.
Before claiming an engine change works, run one real document through it and
record time, translated share, kept-source reasons and formula integrity, as
`docs/bao-cao/do-luong-ollama-2026-10-27.md` does. Compare math-font glyphs
(CMMI/CMSY/CMEX/CMBX) between source and output per page: none may be lost.

## PDF Gate

Keep source and output hashes/paths separate. For every delivered PDF:

1. Reopen it and require the same page count and canvas sizes as the source.
2. Search extracted text for `{vN}`, `<bN>`, `<sN>`, `U+0000`, and `U+FFFD`.
3. Check span boxes against the page canvas and cell text against detected cell
   boundaries. Extraction is diagnostic, not proof of visual correctness.
4. Render every page. Review contact sheets for global anomalies, then inspect
   formula-, table-, rotation-, style-, first/middle/last-page regressions at
   readable resolution.
5. Confirm formulas, technical identifiers, URLs, figures, borders, bullets,
   bold/italic runs, and page numbers remain legible and correctly placed.
6. Report every fallback segment or materially untranslated region as partial.

Use `_workspace/scratch/` for render/diagnostic intermediates and
`_workspace/output/` for final PDFs; both are gitignored. Never overwrite a source or an existing user output without explicit
authorization. For expensive translations, validate representative pages
first, then regenerate the complete document with the final code.
