# Đặc tả xử lý bug sau audit

## Mục tiêu và tương thích

Giữ kiến trúc UI → FastAPI → job → CLI/core → translator/cache. Không thêm service hoặc migration DB nếu không có bằng chứng cần thiết. DTO bổ sung trường có mặc định phù hợp; cập nhật frontend cùng lượt. Không đưa phụ thuộc engine offline vào root chỉ để sửa CORS/cache.

Cache kiểm tra marker trước ghi và khi đọc cache cũ; revision không thay thế validation. Android ưu tiên từ chối an toàn đoạn quá dài và giữ đủ nguồn, chưa mở rộng sang chunking ngữ nghĩa. Cache Android cũ chứa phần đầu dưới khóa toàn văn phải được cách ly có chọn lọc hoặc bằng revision.

## Gate nghiệm thu

- Python 3.12/venv đúng cwd, temp/cache riêng; full unittest, pip check, Ruff E9/F63/F7/F82 và git diff --check trên cây bị sửa.
- Frontend typecheck/build; Electron production loadFile, preload, cổng/token thực tế; upload → job → download; token sai/thiếu và origin không hợp lệ bị xử lý đúng.
- Viewer: nhiều trang, hai khung khác kích thước, gutter, Ctrl-wheel, kéo chuột và canvas gần viewport.
- Android unit test + debug build theo toolchain pinned, emulator/thiết bị xác nhận PDF đoạn dài. Thiếu SDK/thiết bị ghi blocked.
- PDF khoa học, bảng, rotation, scan, references: hash nguồn bất biến, trang/canvas không đổi, không lộ marker, giữ glyph/style/glossary và render các trang liên quan. Mẫu 9 trang kiểm toàn bộ khi có nguồn/tài nguyên phù hợp.
- Chạy lại full offline suite/Chromium nếu thay cây offline có liên quan; timeout có log, không dùng kết quả lịch sử hoặc sửa test để ép pass. Gate bị chặn vẫn chưa nghiệm thu.
- Native smoke khi đổi startup/backend/packaging. Windows sạch/laptop vẫn thuộc gate P7 offline.

## Điều kiện đóng bug

Có repro trước sửa, regression sau sửa, log và ảnh tương ứng. Các bản sửa có trong offline chưa đồng nghĩa root đã sửa. Không đổi phiên bản runtime trong bước lập kế hoạch; không commit/merge/tag/release.
