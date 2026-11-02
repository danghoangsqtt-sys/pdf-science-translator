# Repository and Development

## Structure

For the end-to-end component map and desktop/API/Android boundaries, see
[`docs/codebase-architecture.md`](../docs/codebase-architecture.md).

- `app/`: CustomTkinter GUI, the self-updater, UI fonts, icons, bundled assets.
  `app/update.py` also carries the PowerShell helper that performs the swap.
- `scripts/translate_pdf.py`: supported CLI and stable output staging.
- `webui/`: Electron + React frontend (`frontend/src`) and the FastAPI backend
  (`backend/main.py`, `backend/services/`) it starts on a private 127.0.0.1 port.
  `/api/capabilities` reports the three public profiles; `/api/engines` returns 410.
  Jobs accept `profile`, refuse engine/model/unknown fields, and report the translated share.
  The development launcher prefers `.venv312` before `.venv`; the packaged
  app continues to use its bundled `python_runtime`.
- `scripts/fetch_assets.py`: downloads the layout model and Unicode PDF font.
- `scripts/prepare_offline_pack.py`: assembles verified resources already on disk.
- `scripts/build_offline_windows.py`: fresh portable Electron/Python 3.12/data assembly;
  no network fetch, no overwrite of an existing destination. See the offline handoff doc.
- `pdf2zh/`: bundled extraction, translation, preservation, and PDF rendering.
- `tests/`: standard-library `unittest` regressions.
- `references/`: product preservation contract.
- `app.spec`, `build.ps1`: Windows packaging.
- `app-macos.spec`, `build-macos.sh`: native macOS packaging.
- `.github/workflows/`: release and on-demand macOS builds.

## Commands

For the Windows offline edition use `.venv312/Scripts/python.exe` (Python 3.12).
Build frontend first, prepare a pack from local resources, then run the portable
assembly script. The commands below also document the legacy desktop workflow.
The offline packaged marker and backend launcher prohibit cloud/update paths.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt
.\.venv\Scripts\python.exe app\gui.py
.\.venv\Scripts\python.exe scripts\translate_pdf.py INPUT.pdf --output-dir OUT
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/python app/gui.py
.venv/bin/python scripts/translate_pdf.py INPUT.pdf --output-dir OUT
.venv/bin/python -m unittest discover -s tests -v
bash build-macos.sh
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
