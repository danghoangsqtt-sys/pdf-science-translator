# Repository and Development

## Structure

- `webui/`: the desktop app. `webui/frontend` is the Electron + React
  renderer, `webui/backend` the local FastAPI job server it spawns.
- `app/errors.py`: user-facing failure codes and the copyable error report.
- `app/assets/`: layout model and Unicode font filled by `fetch_assets.py`;
  the Electron installer packages them from here.
- `scripts/translate_pdf.py`: supported CLI and stable output staging.
- `webui/`: Electron + React frontend (`frontend/src`) and the FastAPI backend
  (`backend/main.py`, `backend/services/`) it starts on 127.0.0.1:8089.
  `/api/engines` reports engine readiness; jobs report the translated share.
- `scripts/fetch_assets.py`: downloads the layout model and Unicode PDF font.
- `pdf2zh/`: bundled extraction, translation, preservation, and PDF rendering.
- `tests/`: standard-library `unittest` regressions.
- `references/`: product preservation contract.
- `.github/workflows/`: Android builds only; the desktop app has no release
  workflow yet.

The CustomTkinter GUI, its self-updater and PyInstaller packaging were
removed on 2026-10-29 in favour of `webui/`. Do not reintroduce them.

## Commands

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r webui\requirements-webui.txt
.\.venv\Scripts\python.exe scripts\fetch_assets.py
.\.venv\Scripts\python.exe scripts\translate_pdf.py INPUT.pdf --output-dir OUT
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd webui\frontend; npm install; npm run dev
```

macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/translate_pdf.py INPUT.pdf --output-dir OUT
.venv/bin/python -m unittest discover -s tests -v
```

## Code and Tests

Use four-space indentation, type annotations, concise docstrings,
`snake_case`, `PascalCase`, and `UPPER_CASE`. Prefer `pathlib.Path`, explicit
exceptions, and small helpers whose geometry can be unit-tested. Match nearby
imports and style; there is no repository-wide formatter.

Name tests `test_<feature>.py`, classes `<Feature>Tests`, and methods
`test_<behavior>`. Test observable behavior rather than comments or exact
implementation text. Preserve unrelated dirty-worktree changes.

Commit subjects are short and imperative. PRs state user impact, validation,
and representative visual evidence for GUI/PDF changes. Never commit local
test PDFs or packaged artifacts.
