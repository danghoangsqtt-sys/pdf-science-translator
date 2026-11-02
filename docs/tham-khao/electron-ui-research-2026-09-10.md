# Nghiên cứu: chuyển giao diện desktop sang Electron/React

- **Câu hỏi gốc:** cần đọc song song PDF gốc + bản dịch trong app, và muốn
  giao diện chuyên nghiệp/hiện đại hơn CustomTkinter hiện tại.
- **Nguồn nghiên cứu:** đọc trực tiếp code + tài liệu kỹ thuật thật của dự án
  song sinh `D:\DataAdmin\mdconverter\dhsystem_mdconverter` ("Mark Tini") —
  cùng tác giả, cùng đối tượng người dùng (đọc tài liệu khoa học tiếng Anh),
  đã build/cài/chạy thật (không phải đọc code suông), có báo cáo kỹ thuật chi
  tiết (`docs/bao-cao-ky-thuat-v1.3.0.md`, 613 dòng) ghi lại cả lỗi đã gặp khi
  đóng gói thật.

## 1. Kiến trúc Mark Tini đã kiểm chứng

```
Electron (vỏ desktop) → React UI → HTTP + token → FastAPI (Python, 127.0.0.1:8088)
                                                        → hàng đợi 1 worker → engine xử lý
```

- Electron mở cửa sổ ngay lập tức, **không đợi backend** — React tự poll
  `/api/health` mỗi 1.2s cho tới khi `ready`.
- Backend là **1 tiến trình Python** (FastAPI/uvicorn) do Electron `spawn`,
  không phải microservice/database riêng. Trạng thái job giữ trong RAM tiến
  trình; lịch sử ghi ra file JSON nguyên tử (ghi file tạm → fsync →
  `os.replace`).
- **Bảo mật đã làm đúng chuẩn app desktop 1 người dùng:** token phiên 32-byte
  sinh mới mỗi lần mở app, backend chỉ bind `127.0.0.1` (không lộ ra LAN),
  kiểm tra magic bytes file thật (không tin đuôi file), tên file lưu trên đĩa
  luôn là UUID (chống path traversal), `contextIsolation: true` +
  `nodeIntegration: false` + `sandbox: true` cho renderer.
- **Hàng đợi 1 worker tuần tự** — quyết định có chủ đích để tránh tranh chấp
  RAM/CPU trên máy cá nhân, không phải giới hạn kỹ thuật tạm thời. Hủy job an
  toàn kiểu cooperative (đặt cờ, job tự dừng ở điểm kiểm tra an toàn) thay vì
  giết tiến trình.
- **Electron giám sát và tự khởi động lại backend** nếu crash ngoài ý muốn:
  backoff cấp số nhân (1s→2s→4s...tối đa 30s), tối đa 5 lần, reset ngân sách
  thử lại nếu backend chạy ổn định được 30s. Đóng app dùng `taskkill /f /t`
  để không sót tiến trình Python ngầm.
- **API dạng submit-rồi-poll**, không giữ kết nối mở: `POST /api/jobs` → 202 +
  `job_id` → `GET /api/jobs/{id}` mỗi 750ms → `GET /api/jobs/{id}/result` khi
  `complete`. Đóng/mở lại cửa sổ giữa chừng không làm hỏng job đang chạy nền.
- **Giao diện đọc:** 3 chế độ xem (chỉ soạn thảo / soạn thảo+xem trước song
  song / chỉ xem trước), sidebar thu gọn (56px)/kéo giãn tự do (200–420px),
  trạng thái nhớ qua `localStorage`. Khung xem PDF nhúng thật
  (`PdfViewerBox.tsx`, dùng `react-pdf`/PDF.js), không mở app ngoài.
- **Dịch có che công thức/thuật ngữ, tự lùi lại nếu hỏng:** che `{v0}`,
  `{TERM0}`... trước khi dịch, sau khi dịch kiểm tra nhãn còn nguyên
  đúng số lượng/thứ tự; nếu không khớp thì **tự dịch lại nguyên văn bản gốc
  không che** thay vì trả bản có công thức hỏng — triết lý khác một chút so
  với `pdf2zh/translator.py` hiện tại (đang chọn "bỏ đoạn đó, giữ tiếng Anh"
  thay vì "dịch lại không che" — đáng cân nhắc cho A2 sau này, không chỉ cho
  việc đổi giao diện).
- **4 bộ từ điển thuật ngữ chuyên ngành tĩnh** (CNTT/AI, Toán-Lý-Hóa, Kinh
  tế/XH — 30-36 thuật ngữ/bộ), người dùng tự chọn lĩnh vực khi dịch — **đơn
  giản hơn nhiều** so với hướng "LLM tự nhận diện lĩnh vực" đã lên ở Phase C
  của `vp-pdf`. Đáng cân nhắc làm Phase C theo cách này trước, rẻ và tất định
  hơn LLM.

## 2. Ánh xạ sang `vp-pdf` — cái gì tái dùng được, cái gì phải viết mới

| Phần | Tái dùng được từ Mark Tini | Cần viết mới cho vp-pdf |
| --- | --- | --- |
| Electron main.ts (spawn Python, token, backoff, EPIPE guard, path resolution dev/packaged) | Gần như nguyên khối — không phụ thuộc Docling, thuần hạ tầng Electron | Đổi tên biến/token, đường dẫn `_internal`/`PDFTranslate.exe` hiện tại |
| FastAPI job-queue pattern (submit/poll/result/cancel, ghi file nguyên tử) | Kiến trúc và endpoint shape | Job function đổi thành `translate_pdf()` đã có sẵn trong `scripts/translate_pdf.py` — **đã có sẵn tham số `on_progress`**, khớp gần như thẳng vào pattern polling này |
| Bảo mật (token, localhost-only, magic-byte check, UUID filename) | Toàn bộ | Không cần sửa gì nhiều, logic chung |
| `PdfViewerBox.tsx` (xem PDF nhúng) | Component lõi (react-pdf/PDF.js) | Dùng 2 instance song song (gốc + dịch) thay vì 1; bỏ phần vẽ khung chọn vùng OCR (không cần cho vp-pdf) |
| 3 chế độ xem + sidebar thu gọn | Toàn bộ pattern UI | Đổi nội dung 3 chế độ thành "chỉ gốc / song song / chỉ bản dịch" |
| Dịch che công thức + tự lùi lại | Ý tưởng thiết kế | vp-pdf đã có `encode_formula_placeholders`/`validate_style_tags` riêng — không copy code, chỉ tham khảo chiến lược fallback |
| Docling, EasyOCR, envit5-translation, OpenAlex, Ollama | Không liên quan | vp-pdf giữ nguyên `pdf2zh/` hiện có làm engine |

**Kết luận quan trọng:** phần **hạ tầng Electron ↔ Python** (70% khối lượng kỹ
thuật khó nhất — spawn process, token, backoff, đóng gói, bảo mật) gần như
tái dùng được nguyên khối. Phần phải viết thật sự mới chỉ là: bọc
`translate_pdf()` bằng FastAPI theo đúng pattern đó, và UI xem PDF song song.

## 3. Chi phí thực tế cần biết trước khi quyết — số liệu đo thật, không ước lượng

| | CustomTkinter hiện tại (`vp-pdf`) | Mark Tini (Electron, tham chiếu) |
| --- | --- | --- |
| Dung lượng cài đặt | ~336 MB (zip) | ~1,9 GB installer → **~4,3 GB** sau cài |
| RAM khuyến nghị | Không ghi nhận yêu cầu đặc biệt | **Tối thiểu 8 GB, khuyến nghị 16 GB** |
| Cần quyền admin | Không | Không |
| Model AI đóng gói | ~90 MB (layout + font) + OCR RapidOCR | ~2,3 GB (5 model khác nhau) |

vp-pdf sẽ **nhẹ hơn Mark Tini nhiều** (không cần TableFormer/CodeFormulaV2/
EasyOCR-đa-ngôn-ngữ/model dịch riêng — dùng Google/Handoff có sẵn), nhưng
riêng **runtime Python đóng gói + Electron/Chromium** đã cộng thêm khoảng
**700MB–1,5GB** so với bản CustomTkinter hiện tại, dù giữ nguyên model AI
đang có. Đây là đánh đổi thật, không tránh được nếu chọn Electron.

**Lỗi đã gặp thật khi đóng gói (đáng biết trước để không lặp lại):**
- PowerShell nuốt dấu ngoặc kép khi script đóng gói copy model — sinh đường
  dẫn sai, chỉ phát hiện qua build thật.
- Xung đột định dạng module ESM/CommonJS khi đóng gói Electron main process —
  **app crash ngay khi mở, sau khi cài xong** — lỗi nghiêm trọng, chỉ lộ ra
  khi cài trên máy thật, không thấy khi chạy dev.
- Đến thời điểm báo cáo, Mark Tini **chưa từng được test trên máy Windows
  sạch hoàn toàn** (chưa cài Python/Node) — nghĩa là ngay cả dự án tham chiếu
  cũng chưa xác nhận đóng gói hoạt động 100% ngoài máy dev.

## 4. Khuyến nghị

1. **Khả thi và đáng làm nếu ưu tiên là giao diện chuyên nghiệp** — phần khó
   nhất (hạ tầng Electron↔Python) đã có sẵn mẫu chạy thật để tham khảo, không
   phải mò từ đầu.
2. **Nhưng đây là dự án lớn, nên làm theo phase, không đại tu 1 lần:**
   - Phase UI-1: dựng FastAPI bọc `translate_pdf()` theo đúng pattern
     job-queue của Mark Tini (không đụng `pdf2zh/`).
   - Phase UI-2: Electron shell + màn hình dịch cơ bản (thay thế đúng chức
     năng GUI hiện có, chưa thêm gì mới).
   - Phase UI-3: khung xem PDF song song (tính năng mới thật sự).
   - Mỗi phase build và **cài thử trên máy sạch** trước khi sang phase sau —
     đúng bài học "chưa test máy sạch" ở trên.
3. Việc này **độc lập** với Phase A/B/C đã lên trước đó (sửa lỗi pipeline,
   engine LLM) — có thể làm song song, không chặn nhau, nhưng là khối lượng
   công việc lớn hơn cả 4 phase kia cộng lại.

Chưa code gì ở bước này — đây là tài liệu nghiên cứu để bạn quyết định trước
khi bắt tay vào phase nào.
