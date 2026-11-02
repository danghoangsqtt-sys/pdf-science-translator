# Changelog

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
Nguồn thực: docs/offline-windows-2026-10-28.md và báo cáo cleanup ở checkout IDE.
File changelog trước đó không còn trong checkout tại lúc lập kế hoạch; phần lịch
sử này chỉ tái dựng từ bằng chứng đã có, không giả khôi phục nội dung chưa biết.

