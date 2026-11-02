# Phase 1 execution summary — 30/10/2026

## Outcome

BUG-009, BUG-010, BUG-012 and BUG-013 are technically verified. BUG-011 is implemented: Android rejects a request over 5,000 UTF-16 code units and the PDF caller retains the complete source paragraph on failure. Its Gradle verification is blocked by the machine environment.

## Product changes

- Electron file-origin `null` is allowed by CORS while API token authentication remains mandatory.
- Translation results now carry total/translated counts, ratio, kept reasons, scan pages and Vietnamese warnings through backend and frontend.
- A document with zero successfully translated segments is rejected instead of being presented as complete.
- Formula, style and glossary markers are validated on cache reads and writes; legacy damaged cache rows are ignored without deleting the cache.
- `PDF2ZH_CACHE_DIR` permits a writable application/test cache location while preserving the original user-cache fallback.
- Android no longer calls `query.take(5000)` and keeps the full source text when the request is too long.

## Verification

- Python 3.12.15: 306/306 unittest passed in 10.378 seconds.
- Focused CORS/token/partial/cache suite: passed.
- `pip check`: no broken requirements.
- Ruff hard errors E9/F63/F7/F82: passed.
- Electron/React production build: passed (`tsc -b`, Vite renderer/main/preload).
- `git diff --check`: passed.
- No layout, glyph operator or PDF drawing code changed, so no new translation/render run was required for this bug-only phase.

## Blockers and limits

- The installed Android SDK has platforms 23, 29, 31, 34, 36 and 36.1, but the project requires 35.
- Offline Gradle also lacks the Android/Kotlin/Compose/OkHttp/PDFBox dependency artifacts. Network policy cannot fetch them.
- A temporary compileSdk 36 validation copy reached dependency resolution but could not compile for the same missing artifacts; product files kept compileSdk 35.
- No commit, tag or push was created. The dirty worktree includes unrelated user changes, so ViePilot strict Git persistence cannot pass.