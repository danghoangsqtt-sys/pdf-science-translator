# Repository and Development

## Structure

For the end-to-end component map and desktop/API/Android boundaries, see
[`docs/kien-truc/codebase-architecture.md`](../docs/kien-truc/codebase-architecture.md).

- `app/errors.py`: user-facing failure codes and the copyable error report.
- `backend/app/assets/`, `backend/app/fonts/`: layout model, Unicode PDF font and OCR font;
  the offline build packages them from here.
- `backend/scripts/translate_pdf.py`: supported CLI and stable output staging.
- `webui/`: Electron + React frontend (`frontend/src`) and the FastAPI backend
  (`backend/main.py`, `backend/services/`) it starts on a private 127.0.0.1 port.
  `/api/capabilities` reports the three public profiles; `/api/engines` returns 410.
  Jobs accept `profile`, refuse engine/model/unknown fields, and report the translated share.
  The development launcher prefers `.venv312` before `.venv`; the packaged
  app continues to use its bundled `python_runtime`.
- `backend/scripts/fetch_assets.py`: downloads the layout model and Unicode PDF font.
- `backend/scripts/prepare_offline_pack.py`: assembles verified resources already on disk.
- `backend/scripts/build_offline_windows.py`: fresh portable Electron/Python 3.12/data assembly;
  no network fetch, no overwrite of an existing destination. See the offline handoff doc.
- `backend/pdf2zh/`: bundled extraction, translation, preservation, and PDF rendering.
- `backend/tests/`: standard-library `unittest` regressions.
- `references/`: product preservation contract.
- `docs/`: grouped by kind (`huong-dan`, `kien-truc`, `bao-cao`, `ke-hoach`,
  `tham-khao`; `brainstorm` stays where ViePilot expects it). Evidence under
  `docs/bao-cao/bang-chung/` is a historical record; never rewrite it.
  [`docs/README.md`](../docs/README.md) is the index.

The whole project lives in this one folder. What is not source stays in two
gitignored folders at the root: `_workspace/` (`samples/`, `output/`,
`scratch/`, `backup-*/`) and `BAN-CAI-DAT/` (installable editions). Intermediate
data packs are build input only; put them in `_workspace/scratch/` and delete
them after the build, since they duplicate the model store. Do not recreate
`tmp/`, `output/`, `test_samples/` or `test_output/` at the repository root.
- `.github/workflows/`: Android builds only; the desktop app has no release
  workflow yet.

The CustomTkinter GUI, its self-updater and PyInstaller packaging were
removed on 2026-10-29 in favour of `webui/`. Do not reintroduce them.

## Commands

For the Windows offline edition use `.venv312/Scripts/python.exe` (Python 3.12).
Build frontend first, prepare a pack from local resources, then run the portable
assembly script.
The offline packaged marker and backend launcher prohibit cloud/update paths.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend\requirements-webui.txt
.\.venv\Scripts\python.exe scripts\fetch_assets.py
.\.venv\Scripts\python.exe scripts\translate_pdf.py INPUT.pdf --output-dir OUT
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend; npm install; npm run dev
```

macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python backend/scripts/translate_pdf.py INPUT.pdf --output-dir OUT
.venv/bin/python -m unittest discover -s tests -v
```

### Backend API token

`npm run dev` starts Electron, which passes a fresh token to the backend and
renderer on every launch. A backend started on its own (`python
backend/server/run_server.py`) without `PDFTRANSLATE_API_TOKEN` picks a random
token and answers nobody; set `PDFTRANSLATE_DEV=1` to accept the dev token that
a plain Vite page (`http://localhost:5173`) sends. CORS allows only the
packaged `file://` renderer (origin `null`) and the Vite dev server.

Each job's upload is deleted when the job ends; the last five finished jobs
keep their output, and startup clears both folders, since jobs are in memory only.

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

## Folder Layout (2026-11-09)

- `backend/` — Python import root: `pdf2zh/` engine, `server/` FastAPI app
  (was `webui/backend`), `scripts/`, `tests/`, `app/` assets/fonts,
  `research/`, `requirements*.txt`. Run tests from `backend/`:
  `..\BAN-CHAY\.venv312\Scripts\python.exe -m unittest discover -s tests -t .`
- `frontend/` — Electron + React desktop UI (was `webui/frontend`) and
  `frontend/android/`.
- `BAN-CAI-DAT/` — built installable editions (gitignored).
- `BAN-CHAY/` — the runtime used on this machine: `.venv312/` and the
  embedded `python_runtime/` (gitignored). Electron dev mode looks there first.
- Packaged apps mirror this: `resources/backend/{pdf2zh,server,scripts,app}`,
  `resources/python_runtime`, `resources/offline-data`.
