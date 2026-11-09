# Nhật ký audit sản phẩm

## VP-AUTO — Phase 8 technical verified (09/11/2026)
- P8-T1..T5 technical_verified: BUG-017, BUG-014, BUG-015, ENH-004.
- 404/404 unittest, ruff, tsc, node 12/12, Chromium 24/24 ở 800×600, 1024×768, 1280×1024, 1366×768, 1920×1080.
- Chưa kiểm tay trong Electron; chưa commit/push/tag (persistence pending_user_scope).

## Evolve — Phase 8 tiến độ + giao diện đa kích thước (09/11/2026)
- Mode: Add Feature kèm sửa lỗi; mục tiêu 0.4.0 giữ nguyên, không bump.
- Audit 09/11 trên `release/0.4.0`: 394/394 unittest, `tsc` đạt; ghi BUG-014..018, ENH-003, ENH-004.
- Phase 8: P8-T1 BUG-017 (job kẹt + UI bỏ theo dõi sau 1 lỗi poll), P8-T2 BUG-014, P8-T3 BUG-015, P8-T4/T5 ENH-004 (máy chiếu 4:3, 5:4).
- Nhánh kế hoạch: `claude/evolve-progress-fixes-responsive-ui` từ `release/0.4.0`; chưa commit/push.
- Next: `/vp-auto --from 8`.

## VP-AUTO — Phase 4 technical verified (28/10/2026)
- BUG-008: 22/22 tệp phục hồi có provenance; source bảo vệ giữ nguyên hash.
- 424/424 unittest, pip/Ruff/diff/smoke, 16/16 Chromium; fresh portable đạt.
- PDF khoa học giữ 123/123 glyph toán; scan portable dịch 4/4 đoạn; render đã xem.
- Phase 5 được mở. Git persistence/PASS vẫn pending_user_scope; không commit/tag/push.
- P5-T1 technical_verified: 37 test đạt; pack v1 thật 1.017 tệp vẫn valid; lite
  v2 chỉ fast và profile hỏng độc lập bị cô lập; Git persistence pending.
- P5-T2 technical_verified: 6/6 test; snapshot RAM/GPU/CPU/disk local, TTL 5s,
  timeout GPU 3s và DTO không định danh. Máy phát triển RTX3060 không thay laptop gate.
- P5-T3 technical_verified: policy key ổn định, probe nền hữu hạn, primary+rescue;
  probe fast/GPU/4K thật đạt. Phase 5 full suite 449/449, pip/Ruff/diff đạt.
- Phase 5 technical_verified; Phase 6 mở. PASS/Git persistence vẫn pending_user_scope.

## Evolve — kế hoạch BUG-008 trước, ENH-002 sau (28/10/2026)
- Mode: Add Feature với prerequisite phục hồi; product target 0.4.0, runtime hiện 0.3.0 chưa đổi.
- Phase 4: 3 task BUG-008; gate source recovery/build trước Phase 5.
- Phase 5: 3 task manifest v2 + device snapshot + bounded probe.
- Phase 6: 4 task policy/cache + lite/full + import offline + UI/API.
- Phase 7: 2 task integration/version + laptop thật; target_verified chỉ khi có số đo laptop.
- 12 task planned, chưa sửa mã chạy hay model. .viepilot/ARCHITECTURE.md là proposed; Paths tính từ checkout ngoại tuyến.
- Giữ baseline/cleanup audit và khóa worktree; không tự commit/push/tag/merge, release hoặc overwrite output.
- Execution plan: execution-plan-2026-10-28.json; next P4-T1 qua vp-auto --from 4.

## Dọn an toàn và đánh giá laptop — 28/10/2026
- Đã xóa đúng allowlist 21.345.852.541 byte; 1.017 tài nguyên có bản giữ lại khớp hash, blob model còn ở kho gốc và portable.
- 26 script nháp cũ đóng ZIP trước khi dọn; 10 PDF dịch thử có nguồn tương ứng giữ nguyên. Không xóa mã nguồn sản phẩm, model gốc, portable, QA cuối hoặc xref IDE đang mở.
- 500 tệp bảo vệ khớp hash; worker retained pack ready 32,34s; sau dọn 421/421 unittest (14,832s), pip check/Ruff đạt.
- Phục hồi liên kết Git và dependency venv còn thiếu, khóa worktree chống prune nhầm. BUG-008 mới: 22 tệp tracked đã thiếu trước audit cần đối chiếu/phục hồi.
- ENH-002 mới: kiểm tra máy và pack nhẹ theo profile cho laptop 3050 4GB/24GB RAM; chưa triển khai.
- Báo cáo: `D:/DataAdmin/vp-pdf/docs/audit-don-dep-va-laptop-2026-10-28.md`. Giữ BUG-007/ENH-001 mở, không ghi lại lịch sử thành đã xử lý.

## Triển khai Windows offline — 28/10/2026
- P1-T1: locally_verified; 14 hồi quy offline, worker/dữ liệu riêng 21,23 GB. Cache thêm digest dữ liệu.
- P2-T1: locally_verified; profile-only UI/API/lỗi, cổng/token từng phiên. Sửa lỗi CSP cổng cố định và trạng thái sẵn sàng giả.
- Gate cuối: 421/421 unittest; pip check/Ruff/native smoke đạt; 16/16 Chromium. Ba mức dịch 12/19, 16/19, 19/19 đoạn, giữ đủ 123 glyph toán.
- P3-T1: delivered_for_review; portable 22,66 GB mở sẵn. Scan thật bắt lỗi thiếu font lớp chữ OCR, đã sửa manifest/đường dẫn và có hồi quy; sau sửa dịch 4/4 đoạn, render đạt.
- Nghiệm thu Windows sạch/VM mất mạng và ma trận phần cứng còn pending. Chi tiết: [báo cáo](../docs/bao-cao/offline-windows-2026-10-28.md).
- Git persistence: pending_user_scope; không gộp thay đổi có sẵn vào commit.

Nhật ký audit được giữ lại; kế hoạch triển khai mới có ROADMAP, phase/task và HANDOFF.
Không suy diễn PASS hoặc tạo tag từ các kết quả kiểm tra cục bộ.

## Decision Log

| Ngày | Quyết định | Nguồn | Trạng thái |
| --- | --- | --- | --- |
| 2026-11-09 | Phase 8 lập kế hoạch: BUG-017, BUG-014, BUG-015, ENH-004; hoãn BUG-016/018, ENH-003. | `vp-evolve` | Planned |
| 2026-10-28 | BUG-008 auto-logged by vp-audit Tier 1/2: thiếu tệp tracked/build/docs từ trước dọn. | `vp-audit` | Backlog |
| 2026-10-28 | ENH-002 auto-logged by vp-audit Tier 3: phân tích máy và gói offline nhẹ cho laptop. | `vp-audit` | Backlog |
| 2026-10-27 | BUG-001: Từ chối câu trả lời Ollama sai kiểu hoặc chưa hoàn tất; cache revision 3. | vp-audit Tier 3 | Đã sửa, có hồi quy |
| 2026-10-27 | BUG-002: Hoàn thiện bảo toàn tham khảo và fallback/cache đang dang dở. | vp-audit Tier 3 | Đã xác minh PDF 9 trang và toàn bộ gate Python 3.12 |
| 2026-10-27 | BUG-003: Giữ vị trí trong khoảng trắng giữa các trang khi đồng bộ khung PDF. | vp-audit Tier 3 | Đã sửa, 12 ca tương tác đạt |
| 2026-10-27 | BUG-004: Gỡ số dòng/test lỗi thời, bổ sung kiến trúc và hướng dẫn fallback/cache. | vp-audit Tier 2 | Đã cập nhật |
| 2026-10-27 | BUG-005: Logo dùng đường dẫn tương đối khi mở Electron bằng file URL. | vp-audit Tier 3 | Đã sửa, thêm kiểm tra ảnh tải được |

Chi tiết và bằng chứng: [audit-report.md](audit-report.md).

## Kiểm tra lại và mở giao diện

| Ngày | Phát hiện / quyết định | Nguồn | Trạng thái |
| --- | --- | --- | --- |
| 2026-10-27 | BUG-006: Electron phát triển ưu tiên venv 3.12 đã kiểm chứng. | vp-audit Tier 3 | Đã sửa và xác nhận trên cửa sổ thật |
| 2026-10-27 | BUG-007: Suite đạt nhưng native smoke mất 109,662 giây. | vp-audit Tier 3 | Mở, cần profile |
| 2026-10-27 | ENH-001: Thuật ngữ ở model chính cần kiểm soát theo domain. | vp-audit Tier 3 | Mở |

Báo cáo mới nhất: [kiểm tra lại và mở giao diện](../docs/bao-cao/kiem-tra-lai-va-mo-giao-dien-2026-10-27.md).

- Execution P4-T1: in_progress; Snapshot and provenance inventory. Git persistence pending_user_scope.

- Execution P4-T1: technical_verified; 22 paths confirmed; source snapshot and protected hashes saved. Git persistence pending_user_scope.

- Execution P4-T2: in_progress; Restore only missing files from verified sources. Git persistence pending_user_scope.

- Execution P4-T2: technical_verified; 22/22 restored; existing protected source hashes unchanged. Git persistence pending_user_scope.

- Execution P4-T3: in_progress; Fresh baseline build and regression gate. Git persistence pending_user_scope.

## Hợp nhất release/0.4.0 — 02/11/2026

- Nhánh `release/0.4.0` gộp ba nguồn: engine offline (`backup/offline-engine-wip-2026-11-02`),
  việc gỡ Tkinter và chân trang tác giả (`claude/vp-audit-codebase-review-74c1fe`), và phần việc
  chưa commit của checkout IDE (`backup/main-checkout-2026-11-02`).
- Phase `01-audit-bugfix` của checkout IDE: BUG-009, BUG-010, BUG-012 đã có sẵn ở engine offline;
  BUG-011 (Android) và `PDF2ZH_CACHE_DIR` được gộp. P1-T5 vẫn chờ Android SDK platform 35.
- Giao diện Tkinter, trình tự cập nhật và đóng gói PyInstaller đã bỏ; ứng dụng desktop chỉ còn Electron offline.
- Tiếp theo: sắp xếp lại cây thư mục, rồi build hai bản Máy mạnh / Máy yếu.
