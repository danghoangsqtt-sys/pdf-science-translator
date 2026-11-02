# Phase 7 — Nghiệm thu portable và laptop (ENH-002)

## Goal
Dựng bản sản phẩm mục tiêu 0.4.0 và chứng minh trên desktop + laptop RTX3050 4GB,
RAM24GB/i7gen12; chỉ tuyên bố phạm vi đã đo. Phụ thuộc Phase 6.

## Tasks
| Task | Kết quả | Phụ thuộc |
| --- | --- | --- |
| P7-T1 | Version metadata, full/lite integration/PDF render | Phase 6 |
| P7-T2 | Công cụ QA local và kết quả laptop thật | T1 + target hardware |

## Version
APP_VERSION hiện 0.3.0 là product baseline. Target feature+fix là 0.4.0 (MINOR).
Lượt evolve chỉ ghi target trong plan/CHANGELOG; đổi nguồn APP_VERSION và metadata
đóng gói ở P7-T1. Frontend package 1.0.0 là metadata component cần đối chiếu, không
tự coi là version sản phẩm để downgrade. PDF core có version độc lập.
Không tạo tag v* hoặc phát hành từ kế hoạch/kiểm thử.

## Ma trận nghiệm thu
| Ca | Nơi đo | Bằng chứng |
| --- | --- | --- |
| V1 full / v2 full / v2 lite | Desktop hiện tại | Source/pack/module/version hashes, readiness, actual local worker |
| Thiếu/corrupt common/profile, unknown driver, ít RAM/VRAM, disk-full | Unit + các bài kiểm soát | Fail closed, source immutable, không leak canary |
| CPU-only, GPU/hybrid, timeout/cancel/import interrupted | Runtime local | Thời gian, status, owned process cleanup, rollback |
| Văn bản/công thức/bảng/scan | Desktop rồi laptop | Tỷ lệ dịch/lý do giữ nguồn, glyph/marker/canvas, render mọi trang |
| Fast/lite lạnh + ≥2 lượt ấm | Laptop thật | Peak RAM/VRAM, driver/runtime, latency, không cloud |
| Windows sạch/ngắt mạng | Máy/VM phù hợp khi có | First-run không cài công cụ AI riêng, full local assets |

Fixture thật lấy từ PDF nguồn đã có trong workspace/audit (đọc-only, ghi hash trước).
Không tải PDF hay dùng lại bản dịch làm nguồn chỉ để dễ pass. Unit fixtures được
tạo bằng code; generated PDF/raster/model/log ở build/tmp/output và không đưa vào Git.

## Kết thúc
- local_verified: đủ gate local và artifact chạy; chưa tương đương target_verified.
- target_verified: có kết quả từ laptop thật, không giả từ GPU desktop giới hạn 4GB.
- Nếu chưa có laptop/Windows sạch: hoàn tất công cụ/checklist/artifact và ghi rõ
  awaiting_target_hardware/remaining_acceptance; không đánh ENH-002 resolved hoàn toàn.
- PASS/persistence là trục riêng; không ép commit/push/tag chưa có phạm vi.
- Model/store/PDF gốc và bộ portable đã xác nhận tốt vẫn giữ nguyên để rollback.

