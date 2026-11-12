# Phase 9 — Không gian đọc: tự ẩn thanh trên, PDF vừa bề rộng

## Goal
Khi đang đọc, PDF chiếm gần trọn chiều cao và vừa bề rộng khung trên mọi màn hình,
kể cả máy chiếu 800×600/1024×768, mà không làm mất nút Dịch, tiến độ hay thông báo.

## Quyết định (người dùng)
D1 tự ẩn khi cuộn · D2 vừa bề rộng mặc định · D3 toàn màn hình để sau.
Mặc định chi tiết: xem brainstorm (phần "Mặc định đề xuất").

## Tasks
| Task | Kết quả | Phụ thuộc |
| --- | --- | --- |
| P9-T1 | Thu phóng `fit-width` mặc định, nút "Vừa khung", tính lại theo `ResizeObserver` | — |
| P9-T2 | Thanh trên + chân trang tự ẩn/hiện, vạch tiến độ mảnh, nút ghim | P9-T1 (thanh ẩn/hiện làm đổi kích thước khung → fit tính lại) |
| P9-T3 | Hồi quy Chromium + cập nhật ca cũ "tài liệu mới về 100%" | T1, T2 |

## Thiết kế
- `pdfViewport.ts`: `fitWidthScale(availableWidth, pageWidths, padding)` thuần → `clampScale`.
- `PdfComparison`: `zoomMode: fit | custom` (chung khi đồng bộ, riêng từng khung khi tắt); zoom tay đặt `custom`.
- `PdfViewerBox`: `ResizeObserver` trên viewport; khi `fit` tính scale, giữ trang đang đọc; nút "Vừa khung", nhãn "Vừa khung" thay % (giữ % trong tooltip).
- `useAutoHideChrome.ts`: nhận delta cuộn từ khung PDF (chỉ cuộn do người dùng, không tính cuộn phản chiếu đồng bộ); ẩn khi tích lũy ≥ 48 px xuống, hiện khi ≥ 24 px lên; chuột y ≤ 8 → hiện; focus vào thanh → hiện; ghim (localStorage, try/catch) → không ẩn; `force` khi chưa có file / có lỗi / có thông báo / job vừa kết thúc.
- `App.tsx`: header + action panel trong một vùng ẩn bằng `max-height` + opacity, transition 200 ms, `motion-reduce:transition-none`, `inert` khi ẩn; footer cùng trạng thái; vạch tiến độ 3 px cố định ở mép trên khi ẩn và đang dịch; nút ghim cạnh "Dịch ngay".
- Không đổi backend, API hay chuỗi thông báo hiện có.

## Gate
- `tsc -b`, `node --test` (thêm ca `fitWidthScale`), `npm run test:viewer` (toàn bộ ca cũ + mới).
- Ảnh chụp 800×600 / 1024×768 / 1366×768 khi đang đọc để người dùng xem.
- Kiểm tay Electron do người dùng. Không commit/push nếu chưa được yêu cầu.
