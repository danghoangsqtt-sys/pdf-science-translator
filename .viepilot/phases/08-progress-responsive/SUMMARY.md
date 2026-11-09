# Phase 8 — Summary (09/11/2026)

Trạng thái: technical_verified. Git persistence: pending_user_scope (chưa commit/push/tag).
Nhánh: `claude/evolve-progress-fixes-responsive-ui` từ `release/0.4.0` (30e37d8).

| Task | Request | Kết quả |
| --- | --- | --- |
| P8-T1 | BUG-017 | Job luôn kết thúc; restart worker không chạy song song; UI thử lại khi lỗi tạm, báo rõ khi backend khởi động lại |
| P8-T2 | BUG-014 | Xóa upload khi job xong, giữ 5 kết quả gần nhất, dọn thư mục khi khởi động |
| P8-T3 | BUG-015 | Không còn `dev-token` mặc định; CORS chỉ renderer của app |
| P8-T4 | ENH-004 | Cửa sổ vừa vùng làm việc, tối thiểu 760×540, maximize trên màn chiếu nhỏ, nhớ vị trí, kéo về khi rút màn hình |
| P8-T5 | ENH-004 | Bố cục gọn, chế độ Bản gốc / Bản dịch / Song song, kiểm thử 5 kích thước |

## Gate
- Backend: 404/404 unittest (`BAN-CHAY/.venv312`), ruff (E9/F63/F7/F82/F401/F841) đạt cho phần đã sửa.
- Frontend: `tsc -b` đạt; `node --test` 12/12; Chromium viewer 24/24 (16 ca cũ + 8 ca mới).
- Môi trường: font `backend/app/assets/GoNotoKurrent-Regular.ttf` (gitignore) phải có trong worktree cho 2 test layout.

## Chưa kiểm
- Chạy thật trong Electron (`npm run dev`) trên máy chiếu hoặc khi đổi độ phân giải Windows.
- Bản đóng gói và PDF thật qua worker offline (thay đổi không đụng engine dịch).
