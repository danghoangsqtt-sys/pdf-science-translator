# Windows ngoại tuyến — bộ đã mở để kiểm tra

Đã triển khai trong worktree `feature/offline-engine`, giữ các thay đổi đang có
của checkout IDE. Giao diện chỉ có **Nhanh / Cân bằng / Chất lượng cao**; bộ xử lý
và dữ liệu đi kèm ứng dụng, không cần cài công cụ AI riêng.

- [Báo cáo triển khai và bằng chứng đầy đủ](../.claude/worktrees/frosty-ritchie-f4e306/docs/offline-windows-2026-10-28.md).
- [Mở ứng dụng Windows portable](../.claude/worktrees/frosty-ritchie-f4e306/build/windows-offline-2026-10-28/PDFTranslate.exe).
- [Bản xem trước và ảnh giao diện thật](../.viepilot/ui-direction/windows-offline-2026-10-27/index.html).
- [Bộ kiến trúc](../.viepilot/architect/windows-offline-2026-10-27/index.html).

Kiểm tra cuối: **421/421 unittest**, **16/16 Chromium**, pip check/Ruff/native
smoke đạt. Ba mức giữ đủ 123 glyph toán ở mẫu khoa học; PDF scan portable dịch
4/4 đoạn sau khi sửa thiếu font OCR. Bộ khoảng 22,66 GB; giữ nguyên cả thư mục.

Chưa nghiệm thu Windows sạch/ngắt mạng vật lý và ma trận phần cứng. Chưa
commit/push/tag/ký số/phát hành. Chi tiết giới hạn và đường dẫn bằng chứng trong báo cáo.
