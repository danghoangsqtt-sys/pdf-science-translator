# Phase 10 — Độ trung thực bản dịch: công thức, trang trộn tham khảo, tiêu đề small-caps

## Goal
Bản dịch không bao giờ làm hỏng công thức, không bỏ sót văn xuôi trên trang có tài liệu
tham khảo, và tiêu đề giữ cỡ chữ gốc — kiểm trên bài 2307.15299v5 người dùng báo lỗi.

## Quyết định (người dùng)
D2 thứ tự: công thức → trang 6 → tiêu đề → (ảnh: Phase 11) · D3 không đụng vào công thức.
Chi tiết: `docs/brainstorm/session-2026-11-12.md`.

## Tasks
| Task | Request | Kết quả | Phụ thuộc |
| --- | --- | --- | --- |
| P10-T1 | BUG-020 | Bảo vệ công thức: dòng công thức giữ nguyên; `f(s)` giữa câu thành một marker; kiểm thứ tự marker | — |
| P10-T2 | BUG-021 | Bỏ việc xóa cả trang khi trang trộn văn xuôi + tham khảo | — |
| P10-T3 | BUG-022 | Tiêu đề small-caps dịch ra giữ cỡ chữ hoa | — |
| P10-T4 | BUG-020..022 | Gate trên PDF thật + hồi quy toàn bộ | T1, T2, T3 |

## Ràng buộc
- Mọi thay đổi trong `backend/pdf2zh/` nhỏ, mỗi lỗi có hồi quy tái hiện hình học/marker/glyph
  (AGENTS.md). Fixture: PDF tổng hợp dựng bằng pymupdf; không commit trang của bài arXiv
  trừ khi người dùng đồng ý (câu hỏi mở trong brainstorm).
- Không đổi frontend/API. Không bump (mục tiêu 0.4.0). Android không hưởng sửa này — ghi chú.
- Không ghi đè `C:\Users\Admin\Downloads\2307.15299v5-vi.pdf`; gate ghi ra `_workspace/output/`.

## Gate
- `python -m unittest discover -s tests -t .` từ `backend/` (venv `BAN-CHAY/.venv312`), Ruff lỗi cứng.
- Dịch lại `C:\Users\Admin\Documents\test\2307.15299v5.pdf` (profile Cân bằng, dev venv):
  trang 6 văn xuôi có tiếng Việt và 26 mục `[n]` khớp nguồn; mọi glyph toán + chuỗi số nguồn
  có mặt trong bản dịch; render trang 2, 4, 6 để người dùng xem.
