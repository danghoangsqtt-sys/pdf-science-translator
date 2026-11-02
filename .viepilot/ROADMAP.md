# Windows Offline — kế hoạch triển khai 28/10/2026

Nguồn quyết định: `D:/DataAdmin/vp-pdf/docs/brainstorm/session-2026-10-27.md`.
Windows trước; offline từ lần mở đầu; Nhanh/Cân bằng/Chất lượng cao; không lộ
danh tính AI qua UI/API/lỗi/log người dùng. Giữ thay đổi người dùng hiện có.

| Phase | Task | Trạng thái |
| --- | --- | --- |
| 1 | P1-T1: policy offline, profile, asset pack, worker lifecycle | locally_verified; persistence pending |
| 2 | P2-T1: API và giao diện mức xử lý, lỗi trung tính | locally_verified; persistence pending |
| 3 | P3-T1: gói Windows, kiểm thử thực tế, tài liệu và bàn giao | delivered_for_review; clean-machine acceptance pending |

## Progress Summary
- 3/3 phần triển khai đã có nguồn và bằng chứng kiểm tra cục bộ; 0/3 PASS theo gate Git.
- 421/421 unittest; pip check/Ruff/smoke đạt; 16/16 Chromium; ba mức dịch thật
  giữ 123/123 glyph toán; scan portable dịch 4/4 đoạn. Gói khoảng 22,66 GB đã mở sẵn.
- Chưa có Windows sạch/VM ngắt mạng hoặc ma trận phần cứng; không suy diễn nghiệm thu phát hành.
- Báo cáo: `docs/bao-cao/offline-windows-2026-10-28.md`.
- Không tạo commit/tag/push hoặc gom thay đổi không thuộc nhiệm vụ. Trạng thái
  kiểm chứng tách khỏi PASS/persistence; chỉ ghi PASS khi đủ gate của skill.

## Kế hoạch bổ sung BUG-008 → ENH-002

Người dùng đã chốt thứ tự; lượt này chỉ lập kế hoạch. Product target 0.4.0, chưa bump mã chạy.

| Phase | Task count | Trạng thái | Gate trước khi bắt đầu |
| --- | --- | --- | --- |
| 4: Phục hồi nguồn và baseline — BUG-008 | 3 | technical_verified; persistence pending | Snapshot audit/recovery; không cần chờ phát hành Phase 3 |
| 5: Nền tảng gói và cấu hình máy — ENH-002 | 3 | technical_verified; persistence pending | P4-T3 technical_verified |
| 6: Tích hợp gói nhẹ và giao diện — ENH-002 | 4 | planned | Phase 5 technical_verified |
| 7: Nghiệm thu portable/laptop — ENH-002 | 2 | planned | Phase 6 technical_verified |

### Thứ tự thực thi

- P4-T1: [P4-T1](phases/04-recovery/tasks/P4-T1.md); technical_verified.
- P4-T2: [P4-T2](phases/04-recovery/tasks/P4-T2.md); technical_verified.
- P4-T3: [P4-T3](phases/04-recovery/tasks/P4-T3.md); technical_verified; Phase 5 unblocked.
- P5-T1: [P5-T1](phases/05-device-foundation/tasks/P5-T1.md); technical_verified.
- P5-T2: [P5-T2](phases/05-device-foundation/tasks/P5-T2.md); technical_verified.
- P5-T3: [P5-T3](phases/05-device-foundation/tasks/P5-T3.md); technical_verified; Phase 6 unblocked.
- P6-T1: [P6-T1](phases/06-laptop-integration/tasks/P6-T1.md); sau P5-T3; planned.
- P6-T2: [P6-T2](phases/06-laptop-integration/tasks/P6-T2.md); sau P6-T1; planned.
- P6-T3: [P6-T3](phases/06-laptop-integration/tasks/P6-T3.md); sau P6-T2; planned.
- P6-T4: [P6-T4](phases/06-laptop-integration/tasks/P6-T4.md); sau P6-T1, P6-T2, P6-T3; planned.
- P7-T1: [P7-T1](phases/07-laptop-acceptance/tasks/P7-T1.md); sau P6-T4; planned.
- P7-T2: [P7-T2](phases/07-laptop-acceptance/tasks/P7-T2.md); sau P7-T1; planned.

### Progress Summary bổ sung

- 12 task bổ sung: 6 task Phase 4–5 đã technical_verified, 6 task Phase 6–7 còn planned. Ba phần triển khai cũ giữ trạng thái lịch sử; chưa task nào đạt PASS do persistence và nghiệm thu phần cứng còn chờ.
- Technical gate cho phép ENH-002 sau phục hồi/build baseline; không tự đánh PASS persistence hoặc ép commit ngoài scope.
- Laptop thật và Windows sạch là các gate vật lý chưa có bằng chứng.
- Canonical execution plan: `execution-plan-2026-10-28.json`; kiến trúc proposed: `ARCHITECTURE.md`.
- Bước thực thi: `vp-auto --from 4` ở checkout feature/offline-engine; không chạy Paths tương đối từ nhánh IDE.

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
