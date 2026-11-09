# Bản đồ mã nguồn và các ranh giới bảo toàn

Ngày đối chiếu: 27/10/2026, nhánh `feature/offline-engine`.

## Luồng dịch

```mermaid
flowchart TD
    E[Electron / React] --> A[FastAPI: main.py]
    A --> J[Hàng đợi: job_service.py]
    J --> C[backend/scripts/translate_pdf.py]
    T[Desktop Tkinter] --> C
    CLI[Dòng lệnh] --> C
    C --> H[high_level.py: bố cục, bảo toàn, trang PDF]
    H --> V[converter.py: đoạn văn, marker, dàn chữ]
    V --> R[translator.py: engine, kiểm tra, cache]
    R --> O[Ollama / Azure / Google / handoff]
    V --> P[pdfinterp.py: giữ đồ họa và glyph gốc]
    P --> OUT[PDF mono riêng + báo cáo phần chưa dịch]
```

| Thành phần | Trách nhiệm và ranh giới |
| --- | --- |
| `backend/scripts/translate_pdf.py` | Xác thực core đi kèm, ngôn ngữ, đầu vào; kiểm tra engine; staging và tên đầu ra ổn định; không ghi đè mặc định. |
| `backend/pdf2zh/high_level.py` | Layout ONNX, ghép ô bảng, trang được bảo toàn, sửa PDF qua bản tạm, tổng hợp báo cáo. |
| `backend/pdf2zh/converter.py` | Ghép glyph, phân đoạn, bảo toàn công thức/kiểu chữ, fit trong vùng an toàn, ghi lý do giữ gốc. |
| `backend/pdf2zh/rules.py` | Quy tắc công thức, bảng, mục lục, chỉ mục, danh mục ký hiệu và tham khảo. |
| `backend/pdf2zh/translator.py` | Registry engine, mạng, thử lại, marker, thuật ngữ, phát hiện kết quả không đáng tin. |
| `backend/pdf2zh/cache.py` | Cache SQLite theo engine, tham số, ngôn ngữ và nội dung; Ollama bổ sung phiên bản xử lý và fallback. |
| `backend/pdf2zh/ocr.py` | OCR cục bộ có điều kiện; không dịch vùng scan không đủ bằng chứng an toàn. |
| `backend/server/services/engine_service.py` | Trạng thái Ollama/Azure và hướng dẫn thiết lập; không nạp mô hình khi hỏi danh sách. |
| `backend/server/services/job_service.py` | Một worker, hủy giữa các trang, tiến độ, tỷ lệ dịch và cảnh báo theo nguyên nhân. |
| `frontend/src/components/PdfComparison.tsx` | Bật/tắt đồng bộ vị trí và zoom giữa hai bản PDF. |
| `frontend/src/components/PdfViewerBox.tsx` | Đọc liên tục, kéo chuột, zoom tại con trỏ, chỉ tạo canvas gần viewport. |
| `app/` | Desktop Tkinter, cập nhật, đóng gói; vẫn chọn Google riêng với mặc định Ollama của CLI/Electron. |
| `frontend/android/` | Engine PDFBox-Android độc lập; không thừa hưởng đầy đủ bảo toàn/OCR từ Python. |

## Những quyết định phải giữ

- Trang/công thức/bảng không an toàn được giữ gốc và báo một phần; không ưu tiên tỷ lệ dịch hơn cấu trúc.
- Công thức dùng `{vN}` nội bộ, chuyển thành `<bN></bN>` khi dịch. Marker kiểu chữ và thuật ngữ cũng được kiểm tra trước khi cache/dựng lại.
- TranslateGemma chỉ gọi mô hình dự phòng sau khi kết quả đầu và các lần cứu marker thất bại. Không có fallback thì giữ gốc; không tự tải mô hình.
- Không dịch được đoạn nào là lỗi, không trả một PDF nguyên gốc dưới nhãn bản dịch hoàn tất.
- Trang được bảo toàn toàn bộ giữ content stream gốc; không subset font đầu ra đang đánh địa chỉ glyph bằng ID.
- Bản đích giữ số trang và canvas. Phần trăm dịch chỉ tính những đoạn có thể gửi dịch, không chứng minh mọi ký tự trong PDF đã được dịch.

## Kiểm chứng và vận hành

Hợp đồng kiểm chứng nằm ở `agent-knowledge/validation.md`. Chạy Python 3.12
trong venv, toàn bộ `unittest`, `pip check`, hard-error Ruff và smoke test.
Với frontend, chạy `npm run test:viewer` trong `frontend/`; trình chạy
loại bỏ `ELECTRON_RUN_AS_NODE` để thực sự kiểm tra Chromium.

Các thay đổi trong worktree này không tự xuất hiện trong checkout
`D:/DataAdmin/vp-pdf` đang ở nhánh `feat/domain-glossary`. Cần xem xét tích hợp
nhánh riêng trước khi đóng gói/phát hành; audit không tạo commit hoặc merge.
