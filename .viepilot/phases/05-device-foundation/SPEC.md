# Phase 5 — Nền tảng gói và cấu hình máy (ENH-002)

## Goal
Có manifest theo profile, snapshot tài nguyên tại chỗ và probe hữu hạn để quyết
định profile nào đủ điều kiện. Chỉ bắt đầu sau P4-T3 technical_verified.

## Tasks
| Task | Kết quả | Phụ thuộc |
| --- | --- | --- |
| P5-T1 | Manifest v2/common/per-profile, v1 reader giữ nguyên | Phase 4 |
| P5-T2 | CPU/RAM/VRAM/driver/ổ trống, unknown-safe | Phase 4, thực hiện sau T1 |
| P5-T3 | Immutable policy và probe async/dedupe/timeout | T1 + T2 |

## Contract
Catalog công khai có fast/balanced/quality. V2 lite chỉ có resource fast, không
giả balanced/quality bằng cách trỏ sang cùng trọng số. Full v1 đang dùng vẫn được
đọc nguyên vẹn. Common hỏng/schema/path không an toàn khóa runtime; profile không
cài/hỏng khóa profile đó, không được sử dụng resource chưa được xác minh.

RAM/VRAM tổng và trống là dữ liệu khác nhau. Unknown không phải 0. Không cộng RAM
vào VRAM, không lấy tên GPU hoặc kích thước file làm kết luận đủ cấu hình. Snapshot
không có serial/UUID, không upload telemetry, không yêu cầu quyền admin hay đổi OS.

Một probe/worker tại một thời điểm và chỉ lúc idle; tối đa 2 thử/profile, 60 giây/thử.
UI/API có trạng thái checking và có thể hủy. Không kill service AI của người dùng.
Dữ liệu gửi probe là mẫu không nhạy cảm; raw worker response được lọc trước public.

## States dự kiến
resource_missing, resource_invalid, hardware_unknown, check_required, checking,
ready, ready_slow, insufficient_resources, check_failed; public reason code/message
Việt hóa, không trả mapping AI/path. State nội bộ không bắt frontend biết model.

## Gate
Các schema/hardware/probe tests đạt, v1 không hồi quy; không có network ngoài loopback.
Quyết định bộ nhớ dựa policy có version và số liệu/probe, chưa gọi đây là hỗ trợ
RTX3050 đã nghiệm thu. Cách đếm/bound token phải được xác minh với binary cụ thể
trước khi cho policy nhỏ chạy đoạn dài trong P6-T1.

