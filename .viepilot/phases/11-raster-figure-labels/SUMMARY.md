# Phase 11 — Summary (24/11/2026)

- **Request:** `ENH-011` (`docs/brainstorm/session-2026-11-12.md`, quyết định E3, D1, D4).
- **Trạng thái:** `technical_verified` — đã commit và push lên `origin/release/0.4.0` và `origin/main` (24/11/2026; chưa tạo tag/Release).

## Thay đổi chính
1. **`backend/pdf2zh/figure_ocr.py`** (module mới, tách biệt hoàn toàn với `ocr.py`):
   - Chọn ảnh raster nhúng `≥ 150×80 px` nằm trong vùng `figure` hoặc `table` dạng ảnh không khớp bảng vector; bỏ qua ảnh dùng chung ngoài vùng hình (`shared_outside_figure_xrefs`) và trang scan (`skip_backing_pages`).
   - Lọc nhãn theo E3/D4: OCR `≥ 0,85`, `≤ 6` từ, từ chối số thuần, vạch chia trục, đơn vị, ký hiệu/biến toán, viết tắt (`MAPE`, `ReLU`, …); phân biệt dòng chú giải đồ thị có vạch màu bên trái (`_has_left_swatch`) với hộp chữ 2 dòng; ước lượng nền/chữ từ vòng viền đồng sắc và dừng mở rộng hộp ngay trước viền/vạch màu.
   - Dịch nhãn qua `translator.translate` + `restore_number_notation` + `numbers_intact`, đo và vẽ phủ chữ tiếng Việt bằng `pymupdf` + `cv2` + font Unicode đóng gói (không thêm dependency ngoài `backend/requirements.txt`), thay đúng `xref` ảnh (`_replace_image_xref`) không để lại tài nguyên rác.
2. **`backend/pdf2zh/rules.py`**, **`high_level.py`**, **`offline.py`**, **`scripts/translate_pdf.py`**, **`server/services/job_service.py`**:
   - Export `is_figure_natural_text`; thu ứng viên ảnh figure trước khi `set_contents` xóa stream trang; nạp RapidOCR lười (fail-soft nếu máy dev chưa cài `rapidocr`).
   - Thêm công tắc `ProcessingProfile.translate_figure_images` (`fast=False`, `balanced=True`, `quality=True`) và cờ CLI `--no-figure-ocr`; báo `figure_labels_translated` / `figure_labels_skipped` trong `TranslationReport` và `Translation`.
3. **Test & tài liệu:**
   - 17 test hồi quy mới trong `test_figure_ocr_eligibility.py`, `test_figure_ocr_render.py`, `test_figure_ocr_pipeline.py`.
   - Cập nhật `agent-knowledge/pdf-engine.md` và `agent-knowledge/regressions.md`.

## Kết quả kiểm chứng
- **Automated gate (`.venv312`):** `462/462` `unittest` đạt (`5,392s`), `pip check` sạch, Ruff hard-error (`E9,F63,F7,F82`) sạch.
- **PDF thật #1 (`C:\Users\Admin\Documents\test\2307.15299v5.pdf` → `_workspace/output/p11/2307.15299v5-vi.pdf`, `translategemma:12b`, 146,4s):**
  - Văn xuôi: `114/114` đoạn dịch (`100%`), `246/246` glyph toán khớp nguồn, 0 marker lỗi / `U+0000` / `U+FFFD`.
  - Hình raster: **69 nhãn đã dịch phủ**, 297 nhãn bỏ qua an toàn (vạch số, độ tin thấp, chữ quá nhỏ).
  - Đã xem trực tiếp render trang 2–5 và 5 ảnh trích xuất tại `_workspace/scratch/p11/`: Fig. 1 (sơ đồ khối + chữ Đúng/Sai đúng màu), Fig. 3 (10/10 hộp kiến trúc giữ nguyên `(24)`, `(64)`, `(36)`), Fig. 4 (`Epochs`, vạch số và đường cong nguyên vẹn), Fig. 5 & 6 (chú giải `giá trị thực tế` / `Giá trị dự đoán` giữ nguyên vạch sao xanh / cộng đỏ và toàn bộ vạch số trục).
- **PDF thật #2 (`_workspace/samples/04_scanned_book_page.pdf` → `_workspace/output/p11/04_scanned_book_page-vi.pdf`, `--ocr standard`, 39,1s):**
  - `3/3` đoạn dịch (`100%`), `OCR (standard): pages 1`, không bị `figure_ocr` can thiệp; đã xem render trang 1.
