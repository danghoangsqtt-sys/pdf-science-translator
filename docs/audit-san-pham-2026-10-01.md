# Audit phục vụ báo cáo sản phẩm — 01/10/2026

## Phạm vi và kết quả

| Tầng `vp-audit` | Kết quả |
| --- | --- |
| 1. Trạng thái ViePilot | Không có thư mục `.viepilot/`, nên không thể đối chiếu TRACKER/ROADMAP/HANDOFF. Repo có các ghi chép brainstorm; không suy diễn trạng thái phase. |
| 2. Tài liệu | README mô tả đúng luồng sử dụng chính, nhưng ghi **278 test hồi quy** trong khi lần chạy hiện tại có **299 test**. Con số trong README đã cũ. |
| 3. Chất lượng/khả năng chạy | 299/299 `unittest` đạt; `pip check`, hard-error Ruff và smoke test GUI đạt. Môi trường `.venv` là Python 3.11.9, trong khi AGENTS.md yêu cầu 3.12. Dịch Google trong ca thử trả HTTP 429; chế độ handoff tạo PDF đầu ra. |
| 4. ViePilot framework | Không áp dụng: đây là repo sản phẩm, không phải repo framework ViePilot. |

## Ca thử PDF tiếng Anh về toán và vật lý

- Mẫu cuối: [`math-physics-final-demo.pdf`](../output/presentation-demo-2026-10-01/math-physics-final-demo.pdf); SHA-256 `4e2cf444bab66fc062839dfe821f35bed37bfd488a1194c907c95b3afd2b86cc`.
- Đầu ra: [`math-physics-final-demo-vi.pdf`](../output/presentation-demo-2026-10-01/math-physics-final-demo-vi.pdf). Handoff còn 0/10 đoạn chưa dịch.
- Hai bản đều 1 trang, khổ 595 × 842 pt; bốn dòng công thức giữ nguyên. Trích xuất không thấy marker `{vN}`, `<bN>`, `<sN>`, ký tự NUL hay U+FFFD; không có span vượt khung trang. Đã render và xem trang nguồn, trang đích ở độ phân giải gấp đôi.
- Ảnh cửa sổ desktop thật: [`app-screenshot-final.png`](../output/presentation-demo-2026-10-01/app-screenshot-final.png). Ảnh cho thấy tài liệu ở hàng đợi, không phải màn hình báo hoàn tất.

## Lưu ý khi báo cáo

Nói rõ ca thử thành công bằng **handoff**. Không dùng nó để khẳng định chế độ Google mặc định đã thành công hoặc toàn bộ PDF khoa học đều được dịch trọn vẹn. Bản dịch đầu ra vẫn giữ phần ký hiệu/đơn vị và footer tiếng Anh của mẫu; đây là vùng không được dịch trong ca thử, cần rà soát khi sử dụng thực tế.

Không tự động tạo request ViePilot vì repo chưa có cấu trúc `.viepilot/` và nhiệm vụ hiện tại là audit để chuẩn bị thuyết trình, không phải khởi tạo quy trình quản lý dự án mới.
