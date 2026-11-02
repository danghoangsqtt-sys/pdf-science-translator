# Prompt cho Gemini — dán nguyên văn phần "PROMPT" bên dưới vào Gemini CLI

## Bối cảnh (đọc trước khi dán cho Gemini, không phải một phần prompt)

- Việc này KHÔNG do tôi (Claude) code trực tiếp — bạn chuyển cho Gemini để
  tiết kiệm thời gian. File này là bản đặc tả chặt để Gemini không tự suy
  diễn/code lỗi.
- Nghiên cứu nền tảng đầy đủ: [`docs/tham-khao/electron-ui-research-2026-09-10.md`](electron-ui-research-2026-09-10.md).
- Sau khi Gemini code xong, **tôi (Claude) sẽ review lại code trước khi bạn
  build/dùng thật** — đừng tự chạy `npm run build:electron` với dữ liệu thật
  trước khi có review.

---

## PROMPT (dán từ đây)

Bạn là một kỹ sư frontend cẩn trọng. Nhiệm vụ: tạo một ứng dụng Electron +
React + TypeScript tối giản cho dự án PDF Translate tại
`D:\DataAdmin\vp-pdf`. Đây là MVP nhỏ nhất có thể chạy được, không phải bản
đầy đủ tính năng. Tuân thủ nghiêm ngặt mọi ràng buộc dưới đây — nếu điều gì
không rõ, DỪNG LẠI và hỏi thay vì tự đoán.

### 1. Ràng buộc cứng — không được vi phạm

- **KHÔNG sửa bất kỳ file nào trong** `D:\DataAdmin\vp-pdf\pdf2zh\`,
  `D:\DataAdmin\vp-pdf\app\`, `D:\DataAdmin\vp-pdf\scripts\translate_pdf.py`.
  Đây là code lõi đã kiểm thử 284 test, có bất biến bảo toàn công thức/bố cục
  nghiêm ngặt. Chỉ được **import và gọi hàm có sẵn**, không viết lại logic
  dịch.
- **KHÔNG cài thêm package Python nào** ngoài `fastapi` và `uvicorn` vào
  `D:\DataAdmin\vp-pdf\.venv`. Không đổi `requirements.txt` hiện có — tạo
  file mới `requirements-webui.txt` liệt kê 2 package đó.
- Toàn bộ code mới nằm trong thư mục mới `D:\DataAdmin\vp-pdf\webui\` —
  không tạo file ở bất kỳ đâu khác trong repo.
- Đây là ứng dụng desktop 1 người dùng chạy trên máy cá nhân, KHÔNG phải
  dịch vụ mạng — backend chỉ bind `127.0.0.1`, không bao giờ `0.0.0.0`.
- Sau khi code xong, chạy thử thật (khởi động backend, khởi động Electron,
  dịch thử 1 file PDF có sẵn ở `D:\DataAdmin\vp-pdf\test_samples\` nếu tồn
  tại) trước khi báo hoàn thành. Không được báo "xong" nếu chỉ đọc code mà
  chưa chạy thật.

### 2. Nguồn tham khảo — copy cấu trúc, không copy logic nghiệp vụ

Có sẵn 1 dự án song sinh cùng tác giả tại `D:\DataAdmin\mdconverter\dhsystem_mdconverter`
— copy đúng PATTERN hạ tầng (không phải business logic) từ các file sau:

| Copy pattern từ | File nguồn | Mục đích |
| --- | --- | --- |
| Cách Electron spawn tiến trình Python, sinh token, tự khởi động lại khi crash (backoff), dọn tiến trình khi đóng app | `frontend/electron/main.ts` | Dùng gần như nguyên khối, chỉ đổi tên script Python cần chạy và cổng |
| Cách preload expose token an toàn cho renderer | `frontend/electron/preload.ts` | Copy gần nguyên văn |
| Cấu trúc `package.json` (script build, electron-builder config) | `frontend/package.json` | Đổi `name`, `productName`, `appId` cho đúng PDF Translate, giữ nguyên cấu trúc |
| Cách chạy uvicorn, thêm sys.path cho môi trường đóng gói | `backend/run_server.py` | Copy gần nguyên văn, đổi `src.main:app` → module backend mới, đổi cổng (dùng `8089` để không trùng Mark Tini nếu cả 2 cùng chạy) |
| Component xem PDF nhúng (`react-pdf`) | `frontend/src/components/PdfViewerBox.tsx` | Copy làm điểm khởi đầu, **bỏ hết phần vẽ khung chọn vùng OCR** (`BoundingBox`, `onExtractRegions`, các nút liên quan) — chỉ giữ phần hiển thị PDF cuộn được + zoom |
| Vite + Tailwind config | `frontend/vite.config.ts`, `tailwind.config.js`, `postcss.config.js` | Copy nguyên văn, đổi tên app |

**KHÔNG copy:** Docling, EasyOCR, model dịch `envit5-translation`, citation
verification, markdown editor, autosave IndexedDB, sidebar thu gọn, lịch sử
— không liên quan tới PDF Translate.

### 3. Backend cần tạo — `webui/backend/`

Tạo FastAPI bọc quanh hàm đã có sẵn `translate_pdf()` trong
`scripts/translate_pdf.py` (không sửa file đó, chỉ import).

Chữ ký hàm thật (đã xác nhận, dùng đúng như sau):

```python
def translate_pdf(
    input_pdf: Path,
    output_dir: Path | None,
    *,
    target_language: str = "vi",
    source_language: str = "auto",
    pages: str | None = None,
    threads: int = 4,
    ignore_cache: bool = False,
    overwrite: bool = False,
    engine: str = "google",
    segments: Path | None = None,
    emit_segments: Path | None = None,
    ocr: str = "off",
    on_progress: Callable[[int, int], None] | None = None,
) -> Translation:
```

`Translation` là NamedTuple: `path: Path | None`, `untranslated: int`,
`reasons: Mapping[str, int]`, `image_only_pages: tuple[int, ...]`,
`ocr_pages: tuple[int, ...]`, `ocr_profile: str`, `ocr_warnings: tuple[str, ...]`.

**API cần đúng 4 endpoint sau, không thêm không bớt:**

| Method | Path | Việc làm |
| --- | --- | --- |
| GET | `/api/health` | Trả `{"status": "ready"}` |
| POST | `/api/jobs` | Nhận multipart file PDF + `target_language` (mặc định `vi`). Lưu file vào thư mục tạm với **tên UUID** (không dùng tên gốc, tránh path traversal). Đưa vào hàng đợi **1 worker duy nhất** (copy nguyên lý từ `ConversionJobManager` của Mark Tini — `asyncio.Queue` + 1 task nền, KHÔNG xử lý song song nhiều job). Trả `202` + `{"job_id": "..."}` |
| GET | `/api/jobs/{job_id}` | Trả trạng thái: `{"status": "queued"\|"running"\|"complete"\|"error", "progress": {"done": N, "total": N}, "error": "..." nếu có}`. Trường `progress` lấy từ callback `on_progress(done, total)` truyền vào `translate_pdf()` |
| GET | `/api/jobs/{job_id}/result` | Nếu `status != complete` trả `409`. Nếu xong, trả file PDF đã dịch (`FileResponse`) |

**Bảo mật bắt buộc** (copy nguyên lý từ Mark Tini mục 5.3):
- Sinh 1 token ngẫu nhiên (32 byte, base64url) mỗi lần Electron khởi động,
  truyền cho backend qua biến môi trường `PDFTRANSLATE_API_TOKEN`.
- Mọi endpoint dưới `/api/*` (trừ `/api/health`) yêu cầu header
  `X-PDFTranslate-Token` khớp đúng bằng `secrets.compare_digest`.
- Kiểm tra file tải lên thật sự là PDF bằng magic bytes (`%PDF-`), không tin
  đuôi file.
- Chỉ nhận file `≤ 100 MiB`.

**Chạy thử bắt buộc trước khi báo xong:** `cd D:\DataAdmin\vp-pdf && .venv\Scripts\python.exe -m uvicorn webui.backend.main:app --port 8089`, sau đó gọi `curl http://127.0.0.1:8089/api/health` xác nhận trả JSON đúng.

### 4. Frontend cần tạo — `webui/frontend/`

Một màn hình duy nhất, KHÔNG làm nhiều màn hình/route:

1. Vùng chọn file (drag-drop hoặc bấm chọn), hiển thị tên file đã chọn.
2. Dropdown chọn ngôn ngữ đích — danh sách lấy cứng từ `TARGET_LANGUAGES` (đã
   biết: `af, ca, cs, cy, da, de, en, es, et, eu, fi, fr, ga, gl, hr, hu, id,
   is, it, lt, lv, ms, mt, nl, no, pl, pt, ro, sk, sl, sq, sv, sw, tl, tr, vi`),
   mặc định chọn `vi`.
3. Nút "Dịch" — gọi `POST /api/jobs`, sau đó poll `GET /api/jobs/{id}` mỗi
   750ms (copy đúng khoảng thời gian này từ Mark Tini) cho tới khi
   `complete` hoặc `error`. Hiển thị thanh tiến độ từ `progress.done/total`.
4. Khi `complete`: hiển thị **2 khung `PdfViewerBox` cạnh nhau** (dùng CSS
   grid 2 cột, không cần thư viện split-pane) — bên trái file PDF gốc người
   dùng vừa chọn (giữ trong bộ nhớ `File` object, không cần gọi lại backend),
   bên phải file PDF kết quả tải từ `GET /api/jobs/{id}/result`.
5. Khi `error`: hiển thị đúng nội dung lỗi từ backend, không nuốt lỗi.

Giao diện dùng Tailwind, tối giản, không cần làm đẹp cầu kỳ — placeholder
màu `#14452F` (màu chủ đạo của app hiện tại) cho nút chính là đủ.

### 5. Sau khi xong — báo cáo lại đúng các mục sau, không thêm bớt

1. Danh sách chính xác file đã tạo/sửa (đường dẫn đầy đủ).
2. Xác nhận đã chạy thử thật: backend khởi động thành công, `/api/health`
   trả đúng, đã dịch thử 1 file PDF thật và thấy 2 khung PDF hiện song song.
3. Bất kỳ điểm nào trong prompt này không rõ ràng mà bạn phải tự quyết định
   — liệt kê rõ đã quyết định thế nào và tại sao, để người review biết chỗ
   cần kiểm tra kỹ hơn.
4. KHÔNG tự ý chạy `build.ps1`, KHÔNG tự ý đóng gói `.exe`, KHÔNG tự ý
   commit/push git — dừng lại sau khi code chạy thử được trong môi trường
   dev (`npm run dev` + backend chạy tay).

## PROMPT (kết thúc — dán tới đây)
