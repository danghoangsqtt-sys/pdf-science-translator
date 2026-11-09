# Phase 8 — Tiến độ không kẹt và khung giao diện đa kích thước

## Goal
Sửa tạm các lỗi làm người dùng mất dấu hoặc kẹt tiến độ dịch, chặn tích lũy dữ
liệu và lỗ hổng token, rồi cho cửa sổ ứng dụng dùng được trên màn hình máy chiếu
4:3 và màn gần vuông (5:4). Độc lập với Phase 6–7: không đụng policy/pack/laptop.

## Tasks
| Task | Kết quả | Request | Phụ thuộc |
| --- | --- | --- | --- |
| P8-T1 | Job luôn về trạng thái kết thúc; UI theo dõi bền qua lỗi tạm và backend khởi động lại | BUG-017 | — |
| P8-T2 | Upload/output/job cũ được dọn theo chính sách | BUG-014 | P8-T1 (cùng `job_service.py`) |
| P8-T3 | Không còn token mặc định cố định; CORS hẹp | BUG-015 | — |
| P8-T4 | Cửa sổ Electron theo vùng làm việc màn hình, có kích thước tối thiểu | ENH-004 | — |
| P8-T5 | Bố cục React co giãn + chế độ Gốc/Bản dịch/Song song + QA nhiều kích thước | ENH-004 | P8-T4 |

Thứ tự đề xuất: T1 → T2 → T3 (backend), T4 → T5 (frontend). Nhánh backend và
frontend không chung tệp ngoài `App.tsx` (T1 đụng phần poll, T5 đụng phần bố cục):
làm T1 trước T5.

## Ma trận kích thước (ENH-004)
| Kích thước | Tỷ lệ | Bố cục mong đợi |
| --- | --- | --- |
| 800×600 | 4:3 | Thanh công cụ gọn 1–2 dòng, một khung PDF, chuyển Gốc/Bản dịch |
| 1024×768 | 4:3 | Một khung mặc định; Song song chọn được |
| 1280×1024 | 5:4 | Một khung mặc định; Song song chọn được |
| 1366×768 | 16:9 | Song song mặc định |
| 1920×1080 | 16:9 | Song song mặc định |

Ngưỡng chuyển đề xuất: bề rộng vùng làm việc < 1200 px **hoặc** tỷ lệ < 1,45 thì mặc
định một khung. Người dùng chọn tay thì giữ lựa chọn (localStorage có try/catch).

## Version
Không bump. Mục tiêu sản phẩm vẫn 0.4.0; nguồn phiên bản chuẩn còn mở ở BUG-018.

## Gate kỹ thuật
- `backend`: toàn bộ unittest (`BAN-CHAY/.venv312`), thêm hồi quy cho T1–T3.
- `frontend`: `tsc -b`, `npm run test:viewer` với các ca kích thước mới.
- Thử tay trong Electron (người dùng chạy `npm run dev`; phiên Claude không mở được cửa sổ Electron).
- Không commit/push/tag/merge/phát hành ngoài phạm vi người dùng cho phép.
