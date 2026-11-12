# Changelog

## [Unreleased] — Phase 10 (đã triển khai và kiểm thử kỹ thuật 12/11/2026, chưa commit)

- BUG-020: công thức nội dòng không còn bị viết lại (ngoặc trong `f(s)` đi cùng công thức; dòng công thức giữ nguyên).
- BUG-021: trang có cả văn xuôi và tài liệu tham khảo được dịch phần văn xuôi thay vì giữ nguyên cả trang; danh mục vẫn giữ nguyên dạng sắp chữ.
- BUG-022: tiêu đề chữ hoa nhỏ, tiêu đề bảng và "References" không còn bị co nhỏ: dòng đơn được dùng bề rộng trống của cột.

## [Unreleased] — Chọn ngôn ngữ nguồn (11/11/2026, chưa commit)

- ENH-006: ô "Dịch từ" với Tự nhận diện và 36 ngôn ngữ chữ Latin, nút đảo chiều dịch; dịch được Việt → Anh và ngôn ngữ khác → Việt. Tự nhận diện nhận ra đoạn tiếng Việt thay vì luôn coi là tiếng Anh. Cache bản dịch offline được làm mới một lần (revision 4).

## [Unreleased] — Phase 9 (đã triển khai và kiểm thử kỹ thuật 11/11/2026, chưa commit)

- ENH-005: nút ▲/▼ thu gọn/mở rộng thanh trên và chân trang để mở rộng chỗ đọc (nhớ lựa chọn; cuộn không làm thanh hiện lại, chỉ mở lại khi có lỗi/thông báo/kết quả); PDF mặc định vừa bề rộng khung, có nút "Vừa khung".

## [Unreleased] — Phase 8 (đã triển khai và kiểm thử kỹ thuật 09/11/2026, chưa commit)

- BUG-017: job luôn về trạng thái cuối; giao diện thử lại khi kiểm tra tiến độ lỗi tạm thời và báo rõ khi bộ xử lý khởi động lại.
- BUG-014: dọn tệp tải lên, kết quả và job cũ.
- BUG-015: bỏ token mặc định cố định, thu hẹp CORS.
- ENH-004: cửa sổ và bố cục dùng được trên máy chiếu 4:3, màn 5:4; chế độ xem Gốc / Bản dịch / Song song.

## [Unreleased] — hợp nhất release/0.4.0 (02/11/2026)

### Removed

- Ứng dụng desktop Tkinter, trình tự cập nhật của nó, đóng gói PyInstaller và các workflow
  phát hành chỉ build bản Tkinter. Ứng dụng desktop chỉ còn bản Electron offline.

### Added

- Chân trang bản quyền "© 2026 DHsystem" và hộp giới thiệu tác giả (số điện thoại, mã QR Zalo).

### Fixed (gộp từ checkout IDE, 30/10/2026)

- Android từ chối an toàn đoạn vượt giới hạn thay vì cắt mất phần đuôi (BUG-011).
- Các bản sửa CORS cho Electron đóng gói, cảnh báo dịch một phần và cache marker
  (BUG-009, BUG-010, BUG-012) đã có sẵn ở engine offline.

### Changed

- Hỗ trợ `PDF2ZH_CACHE_DIR` cho cache có vị trí ghi được.

## [Unreleased] — mục tiêu sản phẩm 0.4.0 (đã lập kế hoạch, chưa triển khai)

- BUG-008: đã đối chiếu/phục hồi 22 tệp tracked, thêm build preflight fail-closed
  và dựng fresh portable đạt 424/424 + PDF khoa học/scan; Git persistence pending.
- ENH-002: snapshot CPU/RAM/VRAM/driver/disk, probe local hữu hạn và recommendation theo máy.
- Đã thêm parser manifest v2 common/per-profile, cô lập profile hỏng và đọc nguyên
  gói v1; edition nhẹ chỉ nhận Nhanh, API chặn mức chưa cài bằng lỗi trung tính.
- Đã thêm snapshot cấu hình Windows chỉ đọc: RAM, GPU/VRAM, CPU và disk; TTL năm
  giây, timeout nguồn GPU, trạng thái unknown và không thu UUID/serial/telemetry.
- Đã thêm EffectivePolicy bất biến và device check nền hữu hạn: tối đa hai policy,
  60 giây/probe, dedupe, kiểm tra primary+rescue và chỉ dùng worker sở hữu.
- Policy/token budget/cache theo job, gói nhập từ USB/local và chọn lần mở sau.
- UI giữ Nhanh/Cân bằng/Chất lượng cao, lỗi trung tính và ẩn danh AI.
- Gate laptop RTX3050 4GB/RAM24GB/i7gen12 và Windows sạch tách khỏi kiểm chứng desktop.

Các dòng trên là phạm vi dự kiến. APP_VERSION vẫn 0.3.0; chỉ bump nguồn/metadata
sang 0.4.0 trong P7-T1 khi thực thi. Chưa ký số, commit/push/tag hoặc phát hành.

## Baseline cục bộ đã kiểm chứng trước kế hoạch

Bộ Windows offline hiện tại có profile-only UI/API và worker/data đi kèm. Audit
sau dọn ghi 421/421 unittest; số 16 ca Chromium là bằng chứng từ lượt trước dọn.
Nguồn thực: docs/bao-cao/offline-windows-2026-10-28.md và báo cáo cleanup ở checkout IDE.
File changelog trước đó không còn trong checkout tại lúc lập kế hoạch; phần lịch
sử này chỉ tái dựng từ bằng chứng đã có, không giả khôi phục nội dung chưa biết.

