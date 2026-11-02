# Phase 4 — Phục hồi khả năng dựng và bảo vệ nguồn (BUG-008)

## Goal
Khôi phục đủ 22 tệp tracked đang thiếu theo nguồn gốc rõ ràng, không ghi đè các
thay đổi của người dùng, và dựng được một bộ Windows offline mới từ nguồn.
Đây là điều kiện kỹ thuật bắt buộc trước ENH-002.

## Baseline và phạm vi
- Checkout chuẩn: feature/offline-engine; checkout IDE feat/domain-glossary được giữ.
- Git pointer/venv đã phục hồi, worktree đang khóa; 22 tệp thiếu vẫn phải đối chiếu.
- Không khôi phục nguyên cây HEAD: một số docs/branding/ignore đã có sửa chưa commit.
- Đọc recovery-candidates.json như kết quả khảo sát kế hoạch, kiểm tra lại khi bắt đầu.
- Không tự bỏ khóa, git clean/prune/reset, commit/push/tag/merge hoặc phát hành.

## Tasks
| Task | Kết quả | Phụ thuộc |
| --- | --- | --- |
| P4-T1 | Inventory/provenance/snapshot trước phục hồi | Audit BUG-008 |
| P4-T2 | Phục hồi từng file, ignore và tài liệu đúng hợp đồng | P4-T1 |
| P4-T3 | Build mới + full gate + smoke/render | P4-T2 |

## Gate chuyển Phase 5
- Mọi mục thiếu đã xử lý và có provenance; kiểm tra lại không xuất hiện missing mới.
- Source/branding hiện có và model/PDF nguồn không bị thay ngoài allowlist.
- Python 3.12, toàn bộ unittest, pip check, hard Ruff, TypeScript/Chromium, native smoke đạt.
- Bộ portable mới dùng Python/worker/data của chính nó, dịch/render nguồn hiện có hợp lệ.
- Ghi technical_verified khi có bằng chứng. Git persistence vẫn pending nếu chưa được
  cấp phạm vi; không ép user commit thay đổi ngoài nhiệm vụ để tiếp tục công việc local.

## Resources và rollback
Dùng pack giữ lại ở build/windows-offline-2026-10-28/resources/offline-data làm
đầu vào đọc, không cần tạo lại gói staging đã dọn. Build vào thư mục timestamp mới.
Ước tính phải có hơn 23 GB trống cộng dự phòng trước full-copy; tính lại kích thước
thực, không dựa vào ước tính này để vượt kiểm tra disk. Bộ cũ và backup không bị xóa.
Khi lỗi, quay về executable cũ theo đường dẫn; không restore/overwrite toàn repo.

Bản recovery-verify là artifact tạm do task tạo. Sau khi đạt gate và lưu đủ
manifest/hash/log/render/provenance, có thể dọn bản tạm nếu đã kiểm tra resources
còn bản tốt giữ lại, bằng đường dẫn ownership/allowlist và receipt. Việc này không
cho phép xóa bộ người dùng đã chấp nhận hoặc model store. Mục tiêu tránh giữ thêm
một bản full 23 GB trong suốt các phase sau; không sao chép tiếp nếu thiếu ổ trống.

## Boundaries
Không triển khai nhận diện phần cứng ở phase này. Nguồn build macOS/Android được
giữ nguyên, không yêu cầu chạy hay phát hành bản tương ứng trên Windows.

