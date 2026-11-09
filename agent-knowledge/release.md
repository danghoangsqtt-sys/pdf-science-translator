# Desktop Build and Release

The desktop app is the Electron + React UI in `webui/`. The Android app
releases under the separate `android-v*` namespace; see
[android.md](android.md).

Only publish when the user explicitly requests it.

## Current State

There is no automated desktop release yet. The CustomTkinter app, its
self-updater, `build.ps1`, `build-macos.sh`, the PyInstaller specs and the
`release.yml`/`macos-artifacts.yml` workflows were removed on 2026-10-29.
Before the next desktop release, add: a reproducible `webui/python_runtime`
build, a CI workflow, a packaged smoke test, macOS targets and an updater.

Windows installer, built locally:

```powershell
cd frontend
npm run build
npx electron-builder --win
```

The installer lands in `frontend/release/`. Close any running
`PDF Translate.exe` or backend `python.exe` first; they lock that folder.

## Retired Tkinter Builds Still Poll `v*`

Users on v0.3.x keep checking the latest `v*` release. Their updater downloads
an asset named exactly `PDFTranslate-windows.zip`, accepts it only if
`PDFTranslate.exe` and `_internal/` sit at the archive root, and otherwise
falls back to opening the release page. Therefore:

- Never publish an asset named `PDFTranslate-windows.zip` again. A future
  Electron release must use a different asset name, so old installs only see
  a link to the release page.
- Never tag anything but a desktop release `v*`.

## Third-Party Engines

The user explicitly changed the Windows product scope on 27–28/10/2026 to a
fully offline application with a product-owned worker and complete local data.
For that edition, use `backend/scripts/prepare_offline_pack.py` and
`backend/scripts/build_offline_windows.py`; a separately installed AI service is not a
dependency. Keep original notices/license layers and all generated data out of git.
The private mapping belongs in backend resources, never in user-facing UI/API/logs.
No credentials are bundled. No publication/signing is authorized by local assembly.

The old download-and-swap updater and `build.ps1` payload contract below are for
the legacy desktop release. The new portable app has no online updater and is
not a compatible replacement for that published ZIP until release work is scoped.

## GitHub Flow

1. Commit only source, tests, docs, and version changes on a feature branch.
2. Push, create/update a PR, review exact head SHA, and merge to `main`.
3. Update local `main` with `--ff-only` and verify a clean worktree.
4. Tag and publish only after the release workflow above exists and passes.
