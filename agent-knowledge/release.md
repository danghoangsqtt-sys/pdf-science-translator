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
cd webui\frontend
npm run build
npx electron-builder --win
```

The installer lands in `webui/frontend/release/`. Close any running
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

Never bundle Ollama or a model into an installer or release asset. The app
detects Ollama and tells the user how to install it and run `ollama pull`.
Never ship an Azure key; it is read from the user's environment or settings
file at run time.

## GitHub Flow

1. Commit only source, tests, docs, and version changes on a feature branch.
2. Push, create/update a PR, review exact head SHA, and merge to `main`.
3. Update local `main` with `--ff-only` and verify a clean worktree.
4. Tag and publish only after the release workflow above exists and passes.
