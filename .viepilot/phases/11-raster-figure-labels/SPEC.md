# Phase 11 — Dịch nhãn trong ảnh raster (sơ đồ khối, đồ thị, bảng ảnh)

## Goal
Dịch các nhãn văn bản ngắn nằm trong ảnh raster nhúng thuộc vùng sơ đồ khối, đồ thị và bảng dạng ảnh (khi OCR đủ độ tin và nền đồng nhất), che nhãn gốc bằng màu nền khối và vẽ lại nhãn tiếng Việt bằng font Unicode đóng gói — đồng thời giữ nguyên 100% số liệu, vạch chia trục, đơn vị, ký hiệu, biến toán, viết tắt, công thức và luồng OCR trang scan hiện có.

## Quyết định (người dùng)
- Nguồn: `docs/brainstorm/session-2026-11-12.md` (**E3**, **D1**, **D4**), request `.viepilot/requests/ENH-011.md`.
- **D1:** Dùng RapidOCR sẵn có (`pdf2zh/ocr.py`, offline assets đã xác minh) đọc nhãn, che ô chữ gốc bằng màu nền khối, vẽ nhãn tiếng Việt. Không chắc chắn thì giữ nguyên điểm ảnh gốc.
- **D4:** Dịch nhãn sơ đồ khối, tiêu đề/chú giải/tên trục đồ thị, tiêu đề ô bảng. **Giữ nguyên số liệu**: số, vạch trục, đơn vị, tên biến/ký hiệu, viết tắt (`MAPE`, `ReLU`), giá trị ô bảng; nhãn hỗn hợp (`Dense Layer (64)`) giữ nguyên văn phần số.
- **Ngưỡng E3:** ảnh gốc ≥ 150×80 px nằm trong vùng `figure` (hoặc bảng ảnh không khớp bảng vector); nhãn ngắn ≤ 6 từ; độ tin OCR ≥ 0,85; nền vòng viền quanh nhãn gần đơn sắc; chữ mới cùng màu chữ gốc, vừa ô, không tràn khung; có công tắc tắt theo profile/CLI và báo số nhãn đã phủ/bỏ qua trong báo cáo.

## Tasks
| Task | Request | Kết quả | Phụ thuộc |
| --- | --- | --- | --- |
| P11-T1 | ENH-011 | Module `figure_ocr.py`: chọn ảnh figure, gọi RapidOCR tái dùng, lọc nhãn đủ chuẩn (E3/D4), ước lượng màu nền/chữ | — |
| P11-T2 | ENH-011 | Dịch nhãn bảo toàn số liệu + vẽ phủ Unicode bằng PyMuPDF/OpenCV (không thêm dependency mới), kiểm soát vừa khung | P11-T1 |
| P11-T3 | ENH-011 | Tích hợp vào `high_level.py`, `translate_pdf.py`, `offline.py`, `job_service.py`, công tắc tắt & báo cáo `TranslationReport`/`Translation` | P11-T2 |
| P11-T4 | ENH-011 | Gate hồi quy đầy đủ (`unittest`, `pip check`, Ruff), kiểm PDF thật (`2307.15299v5.pdf` + 1 PDF scan) & cập nhật `agent-knowledge/` | P11-T3 |

## Ràng buộc kiến trúc
- **Không thêm dependency mới:** vẽ chữ Unicode tiếng Việt bằng `pymupdf` (`Font` + `Page.insert_textbox`/`get_pixmap`) kết hợp `numpy` + `cv2` đã ghim trong `backend/requirements.txt` và font đóng gói (`BeVietnamPro-Regular.ttf` / `GoNotoKurrent-Regular.ttf`) để tương thích 100% `BAN-CHAY/python_runtime` và gói offline.
- **Không sửa luồng OCR trang scan (`backend/pdf2zh/ocr.py`):** tách riêng logic ảnh figure sang `backend/pdf2zh/figure_ocr.py`; trang `image_only` / `ocr_preparation.pages` không đi qua bước phủ ảnh figure.
- **An toàn ngoại tuyến & bảo toàn:** không tải model/font qua mạng; không sửa PDF nguồn; không chạm công thức toán hay chuỗi số; ảnh ngoài vùng figure hoặc không có nhãn đạt ngưỡng giữ nguyên byte/xref gốc.
- **Phạm vi sản phẩm:** không đổi public UI/API contract (vẫn 3 profile Nhanh / Cân bằng / Chất lượng cao, không lộ tên AI/engine); không bump version (giữ mục tiêu `0.4.0` tại `frontend/package.json`); Android (`frontend/android/`) là pipeline riêng, không tự hưởng tính năng này.
- **Fixture & đầu ra:** dùng ảnh/PDF tổng hợp dựng bằng `pymupdf` + `cv2` cho unit test (không commit trang bài arXiv); kiểm PDF thật ghi ra `_workspace/output/p11/`, không ghi đè nguồn hoặc tệp trong `Downloads`.

## Gate
- Python 3.12 (`BAN-CHAY/.venv312`): `unittest discover -s tests -t .` từ `backend/`, `pip check`, Ruff hard-error (`E9,F63,F7,F82`) đều đạt.
- Dịch thật `C:\Users\Admin\Documents\test\2307.15299v5.pdf` ra `_workspace/output/p11/2307.15299v5-vi.pdf`:
  - Fig. 1 (tr.2), Fig. 3 (tr.3–4), Fig. 4 (tr.4), Fig. 5–6 (tr.5): nhãn đạt ngưỡng được dịch rõ, không tràn khung; `(36)`, `(64)`, `(24)`, vạch trục, `MAPE`/`ReLU` và toàn bộ glyph toán/số văn xuôi còn nguyên 100%.
  - Kiểm tra thêm 1 PDF scan với `--ocr standard` xác nhận không hồi quy luồng OCR trang scan.
  - Render các trang có hình ra `_workspace/scratch/p11/` và đối chiếu bằng mắt.
