# Task Phase 1

## Objective

Fix BUG-009 through BUG-013 while preserving all pre-existing changes. Expected behavior: packaged Electron reaches the authenticated API; partial output remains downloadable with ratio and reasons; cache never serves damaged formula/style/glossary markers; Android never truncates a paragraph; offline progress reflects current evidence.

## File-Level Plan

- `webui/backend/main.py`: allow production file-origin and permit warning results to download.
- `webui/backend/services/job_service.py`: retain translation audit data and classify partial completion.
- `webui/frontend/src/services/api.ts`, `App.tsx`, `components/TranslationWarningBanner.tsx`: accept the extended DTO and show Vietnamese warnings.
- `scripts/translate_pdf.py`: expose total/translated counts and reject zero-translated output.
- `pdf2zh/translator.py`, `cache.py`: validate cached markers and support a writable cache root.
- `tests/`: regress CORS/token, partial reporting, cache safety, and zero-translated refusal.
- Android engine/preserver/tests: reject over-limit input and preserve complete source fallback.
- Offline `.viepilot/ROADMAP.md`: synchronize the P4–P7 summary only.

## Best Practices

- Keep CORS separate from constant-time token authentication.
- Keep DTO additions optional for frontend/backend compatibility.
- Validate cached data on read and write without deleting the user's cache.
- Preserve the complete source whenever translation cannot be proven safe.
- Use observable regressions and pinned toolchains.

## Verification Commands

- Python 3.12: `python -m unittest discover -s tests -v` → all tests pass.
- `python -m pip check` and Ruff E9/F63/F7/F82 → exit 0.
- `webui/frontend`: `npm run build` → TypeScript/Vite exit 0.
- `android`: `.\gradlew.bat testDebugUnitTest assembleDebug` → exit 0 when SDK 35/dependencies are present.
- `git diff --check` → exit 0.
## Paths

- webui/backend/main.py
- webui/backend/services/job_service.py
- webui/frontend/electron/main.ts
- webui/frontend/src/
- pdf2zh/translator.py
- pdf2zh/cache.py
- scripts/translate_pdf.py
- tests/
- android/app/src/main/java/com/vitranslate/pdf/repository/GoogleTranslateEngine.kt
- android/app/src/main/java/com/vitranslate/pdf/repository/PdfLayoutPreserver.kt
- android/app/src/test/
- .claude/worktrees/frosty-ritchie-f4e306/.viepilot/

## P1-T1 — Baseline (0.5 ngày)

Đọc AGENTS/shared knowledge từng cây trước sửa, gồm pdf-engine/regressions khi sửa preservation. Ghi branch/HEAD, dirty paths, runtime, hash file dự kiến sửa. Đối chiếu patch root/offline và test có sẵn; tái hiện 009/010/011/012. Bảo toàn thay đổi cũ, không đụng output. Gate: xác định được nguồn và checkout đích cho từng patch.

## P1-T2 — BUG-009 (0.5 ngày)

Port tối thiểu CORS file-origin từ offline cùng token hiện có. Test OPTIONS/requested headers, null origin, development HTTP, origin ngoài allowlist, token đúng/sai/thiếu. CORS không thay authentication. Gate: Electron production gọi API được, request không xác thực vẫn bị từ chối; replay từ cửa sổ thật.

## P1-T3 — BUG-012 (0.5–1 ngày)

Guard marker khi cache read/write, tham khảo offline. Test b0→b9, thiếu/trùng formula marker, style/glossary, cache cũ hỏng, cache hợp lệ. Lần gọi sau phải gọi engine lại hoặc fail-safe; không phục vụ kết quả hỏng và không xóa toàn bộ DB. Gate: PDF thật giữ glyph/style và không lộ marker.

## P1-T4 — BUG-010 (0.5–1 ngày)

Giữ translated/untranslated, ratio, kept reasons, image-only và warnings xuyên core/job/API/UI tiếng Việt. Định nghĩa mẫu số ratio và 0/0. Test đầy đủ, partial marker/fit/engine, image-only, zero-translated, lỗi/hủy. Gate: partial hợp lệ tải được nhưng hiện cảnh báo; không có đoạn dịch được thì không báo thành công. Trường DTO tùy chọn có mặc định phù hợp.

## P1-T5 — BUG-011 (0.5–1 ngày)

Bỏ cắt im lặng: từ chối an toàn đoạn vượt giới hạn, caller giữ đủ nguồn và báo untranslated. Không cache phần đầu dưới khóa toàn văn; cách ly cache cũ có nguy cơ bị cắt. Test 4999/5000/5001, Unicode/surrogate, marker ở biên, sentinel cuối đoạn và cancellation. Giữ hợp đồng giới hạn hiện có; chunking là cải tiến sau. Gate: test/build Android riêng và render xác nhận đuôi còn nguyên.

## P1-T6 — BUG-013 (0.25 ngày)

Đọc state offline mới, tính summary từ task hiện hành. Sửa summary và dẫn chứng, giữ nhật ký lịch sử; tách technical_verified, persistence pending và nghiệm thu phần cứng. Không tự hoàn tất P6/P7 hoặc tạo tag.

## P1-T7 — Hồi quy (0.5–1 ngày)

Chạy gate SPEC phù hợp từng cây bị sửa, lưu command/cwd/runtime/exit code/thời gian/hashes/ảnh. Kiểm tra diff với baseline, cập nhật request/TRACKER/state theo kết quả thật. Nếu bị chặn ghi rõ phần chưa nghiệm thu. Không bump APP_VERSION hay phát hành.

## Execution Notes — 30/10/2026

- P1-T1/T2/T3/T4/T6: technical_verified.
- P1-T5: implemented; Android verification blocked by missing platform 35 and dependencies.
- P1-T7: desktop quality gates passed; Android and Git persistence pending.
- Evidence: `../SUMMARY.md`; no commit, tag, push, release, or output overwrite.