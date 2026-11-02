# Phase 4 — Technical verification summary

Status: `technical_verified`; Git persistence: `pending_user_scope`.

## Delivered

- P4-T1: inventory 22 tệp, snapshot hai checkout và hash nguồn/portable bảo vệ.
- P4-T2: phục hồi 22/22 tệp theo từng đường dẫn; giữ branding người dùng và
  hợp đồng Windows offline/Python 3.12; không reset/merge/stage.
- P4-T3: builder fail-closed, ba hồi quy build, fresh portable và PDF QA thực.

## Evidence

- 424/424 unittest; pip check, hard Ruff, diff check và smoke đạt.
- 16/16 Chromium viewer đạt.
- Fresh portable tự dùng Python 3.12/worker/data đi kèm.
- PDF khoa học giữ 123/123 glyph toán; PDF scan dịch 4/4 đoạn; render đã xem.
- Báo cáo: `docs/recovery/bug-008-build-verification.md`.

## Remaining gates

Không ghi PASS/tag vì chưa có phạm vi commit/push và worktree có thay đổi người
dùng cần bảo vệ. Nghiệm thu Windows sạch và laptop thật thuộc Phase 7.

Bản build `build/recovery-verify-20261028` là artifact tạm 22.654.743.222 byte.
Lệnh dọn có kiểm tra allowlist/marker bị cơ chế duyệt tự động từ chối, nên artifact
được giữ nguyên; bộ tốt `build/windows-offline-2026-10-28` không bị thay đổi.
