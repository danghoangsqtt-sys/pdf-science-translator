# Repository and Development

## Structure

The Windows offline implementation currently lives in the separate, protected
worktree `.claude/worktrees/frosty-ritchie-f4e306`; do not treat it as disposable
or merge/delete the IDE checkout's uncommitted changes. See
[`the cleanup audit`](../docs/audit-don-dep-va-laptop-2026-10-28.md) before removing
generated data or choosing which build to run. The verified intermediate data
pack was removed; the complete portable resources and original model store remain.
The audit also records missing tracked build/docs files predating cleanup.

- `app/`: CustomTkinter GUI, the self-updater, UI fonts, icons, bundled assets.
  `app/update.py` also carries the PowerShell helper that performs the swap.
- `scripts/translate_pdf.py`: supported CLI and stable output staging.
- `scripts/fetch_assets.py`: downloads the layout model and Unicode PDF font.
- `pdf2zh/`: bundled extraction, translation, preservation, and PDF rendering.
- `tests/`: standard-library `unittest` regressions.
- `references/`: product preservation contract.
- `app.spec`, `build.ps1`: Windows packaging.
- `app-macos.spec`, `build-macos.sh`: native macOS packaging.
- `.github/workflows/`: release and on-demand macOS builds.

## Commands

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
