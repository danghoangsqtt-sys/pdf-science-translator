# Kế hoạch triển khai: chất lượng dịch chuyên ngành/học thuật

- **Nguồn gốc:** [`docs/brainstorm/session-2026-09-10.md`](brainstorm/session-2026-09-10.md)
  mục 6–8; bằng chứng QA ở
  [`docs/qa-benchmark-report-2026-09-10.md`](qa-benchmark-report-2026-09-10.md).
- **Không tạo `.viepilot/`:** dự án đã có hệ thống tài liệu riêng
  (`agent-knowledge/` + `CLAUDE.md`). Kế hoạch này chỉ là 1 file tham chiếu
  thêm, không thay LICENSE/CONTRIBUTING/CONTRIBUTORS/CHANGELOG/README hiện có.
- **Trạng thái:** chưa triển khai — đánh dấu `[x]` khi hoàn tất từng việc.
  Mỗi phase đọc [`agent-knowledge/index.md`](../agent-knowledge/index.md) để
  biết file kiến thức nào cần đọc trước khi sửa (theo đúng quy ước repo).

## Thứ tự phase

```
Phase A (sửa lỗi pipeline)
        │
        ▼
Phase B (engine LLM) ──► Phase C (nhận diện lĩnh vực, phụ thuộc B)
        │
        ▼ (độc lập, có thể làm song song B/C)
Phase D (preview theo trang trong GUI)
```

---

## Phase A — Sửa 2 lỗi pipeline dịch chung

Đọc trước: [`agent-knowledge/pdf-engine.md`](../agent-knowledge/pdf-engine.md),
[`agent-knowledge/regressions.md`](../agent-knowledge/regressions.md).

### A1. Crash `KeyError: 'N'` trên tài liệu lớn xử lý toàn văn bản

- **Tái hiện:** dịch `test_samples/08_arxiv_xlarge_llm_survey.pdf` (144
  trang) nguyên file bằng CLI mặc định → crash ở ~17/144 trang, không ra
  file. Cùng nội dung qua `--pages 1-20` hoặc `--pages 15-20` thì **không**
  crash — lỗi phụ thuộc trạng thái toàn văn bản, không phải một trang đơn lẻ.
  Log đầy đủ trong `docs/qa-benchmark-report-2026-09-10.md` mục 4.1.
- [x] Xác định vị trí ném `KeyError: 'N'`: **`pdf2zh/pdfinterp.py:231`**,
      trong `init_resources()` → closure `get_colorspace()`. Một tài nguyên
      `ColorSpace` kiểu `ICCBased` trỏ tới một stream hỏng
      (`stream_value()` không raise, nó rơi về một `PDFStream({}, b"")`
      rỗng khi đối tượng không thực sự là stream — khớp với các dòng
      `MuPDF error: format error: object is not a stream` /
      `invalid ICC colorspace` mà chính MuPDF đã báo trên file này) rồi bị
      index thẳng `["N"]` không qua `.get()`. Không tất định theo trang cụ
      thể: 1 trong nhiều lần dịch trọn vẹn 144 trang mới crash, các lần dịch
      theo `--pages` con hoặc lần chạy sạch khác có thể không trúng đúng
      luồng xử lý tài nguyên hỏng đó.
- [x] Viết test hồi quy: [`tests/test_colorspace_resources.py`](../tests/test_colorspace_resources.py)
      — dựng `PDFPageInterpreterEx` tối thiểu với 1 resource `ICCBased` trỏ
      tới stream hỏng, xác nhận trước khi sửa test này bắt đúng
      `KeyError: 'N'` (đã kiểm chứng bằng `git stash` tạm bỏ fix rồi chạy lại
      test), sau khi sửa test pass và không raise.
- [x] Sửa: `get_colorspace()` dùng `.get("N")` thay vì `["N"]`, trả `None`
      (tức "màu không giải thích được", đúng theo triết lý đã có ở
      `agent-knowledge/pdf-engine.md` mục Colour and Emphasis) khi thiếu
      hoặc không phải `int`, thay vì crash toàn bộ tiến trình dịch.
- **Acceptance:** 280/280 test (278 cũ + 2 mới) pass; `ruff`/`pip check`/
  `git diff --check` sạch. `test_samples/08_arxiv_xlarge_llm_survey.pdf`
  dịch trọn vẹn 144 trang thành công trong lần chạy xác nhận (không crash).

### A2. Văn bản lai Anh-Việt bị hỏng, không được cảnh báo

- **Tái hiện:** dịch `test_samples/07_arxiv_large_datacenters.pdf`, trang 23
  chứa đoạn `"...onding Max..."` kẹt giữa câu tiếng Việt (mảnh vỡ của
  "corresponding Maxwell") — không có warning nào được phát ra dù văn bản
  hỏng. Xem `docs/qa-benchmark-report-2026-09-10.md` mục 4.2.
- [x] Tìm bước dựng lại đoạn/trang gây ghép chữ — **đã xác định cơ chế
      chính xác, chưa vá**. Bằng chứng (instrument trực tiếp
      `GoogleTranslator.do_translate`, xem toàn bộ log ở
      `full_traceback`/`all_segments_p23` trong phiên làm việc): câu nguồn
      *"...which establishes the corresponding Maxwell reciprocity relation
      within the present constitutive formulation."* bị bộ dựng đoạn
      (paragraph/run builder trong `converter.py`, khu vực dựng `sstk` từ
      `LTChar`) cắt thành **3 mảnh ngay giữa từ**: `"which establishes the
      corresp"` → dịch riêng; mảnh giữa **`"onding Max"` không hề được gửi
      cho Google** (bị phân loại không-cần-dịch/giữ nguyên, rất có thể do
      nhầm là còn thuộc vùng công thức được bảo vệ của phương trình (60) ngay
      phía trên — đúng loại nhầm lẫn hình học mà
      `agent-knowledge/pdf-engine.md` cảnh báo: "detection also uses
      operators and stacked-token geometry"); mảnh `"well reciprocity
      relation..."` lại được dịch riêng. Ghép 3 mảnh lại đúng như bản dịch
      hỏng đã thấy. **Google Translate không có lỗi** — cả 2 lệnh gọi
      Google đều trả về bản dịch sạch, đã xác minh bằng cách chặn và in
      trực tiếp request/response.
- [ ] Vá điểm phân loại/tách đoạn gây cắt giữa từ trong `converter.py`
      (chưa làm — cần điều tra sâu hơn phần dựng run theo font/hình học,
      rủi ro cao hơn A1 vì đụng đúng logic "đặc sản" của dự án; xem phần
      quyết định tiếp theo trước khi sửa).
- [ ] Tối thiểu: nếu chưa vá được gốc rễ, thêm kiểm tra phát hiện mảnh nguồn
      bị cô lập giữa hai đoạn đã dịch và báo `partial` thay vì báo thành
      công im lặng.
- [ ] Test hồi quy tái hiện hình học tối thiểu gây lỗi (sau khi có hướng vá).
- **Acceptance:** trang 23 của file 07 không còn mảnh vỡ tiếng Anh giữa câu
  tiếng Việt; nếu trường hợp tương tự còn xảy ra ở tài liệu khác, công cụ
  phải báo `partial`, không báo thành công im lặng.

**Verify chung cho Phase A:**
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\translate_pdf.py test_samples\08_arxiv_xlarge_llm_survey.pdf --output-dir test_output --overwrite
.\.venv\Scripts\python.exe scripts\translate_pdf.py test_samples\07_arxiv_large_datacenters.pdf --output-dir test_output --overwrite
```

---

## Phase B — Engine dịch LLM (OpenAI-compatible)

Đọc trước: `pdf2zh/translator.py` (lớp `BaseTranslator`, `GoogleTranslator`,
`HandoffTranslator`, hàm `validate_style_tags`).

- [ ] Thêm `class LlmTranslator(BaseTranslator)` trong `pdf2zh/translator.py`,
      dùng chuẩn OpenAI-compatible (`base_url`, `model`, `api_key`) — cấu
      hình qua biến môi trường hoặc tham số CLI, **không** hard-code khóa API
      nào vào mã nguồn hay commit.
- [ ] Prompt mặc định: yêu cầu giữ nguyên placeholder `{vN}`/`<bN>`/`<sN>` +
      văn phong học thuật tiếng Việt trang trọng. Không tự ý validate lại
      placeholder trong lớp này — tái dùng `validate_style_tags()` sẵn có ở
      lớp gọi chung (đã áp dụng cho Google/Handoff), theo đúng phát hiện kiến
      trúc ở brainstorm mục 7 (khác cách làm "tin prompt suông" không kiểm
      chứng của repo gốc PDFMathTranslate).
- [ ] Thêm `"llm"` vào `ENGINES` trong `scripts/translate_pdf.py` (dòng 42)
      và wiring `--engine llm` + tham số base-url/model/api-key-env.
- [ ] Test: mock HTTP endpoint OpenAI-compatible, không gọi API thật trong
      test hồi quy.
- **Acceptance:** `--engine llm` dịch được 1 file mẫu qua endpoint giả lập
  trong test; placeholder công thức không bị rơi qua `validate_style_tags()`.

**Verify:**
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\translate_pdf.py --help   # xác nhận --engine llm xuất hiện
```

---

## Phase C — Nhận diện lĩnh vực trước khi dịch (phụ thuộc Phase B)

- [ ] Chỉ kích hoạt khi `--engine llm` (Google không nhận custom prompt).
- [ ] Lấy văn bản từ 1–2 trang đầu (tiêu đề + đoạn mở đầu/abstract nếu có).
- [ ] Gọi `LlmTranslator` (hoặc client riêng) với prompt phân loại lĩnh vực
      (vật lý, y khoa, luật, CNTT...) — 1 lần cho cả tài liệu.
- [ ] Nạp kết quả vào system prompt dùng chung cho mọi đoạn dịch sau đó.
- [ ] Cờ tắt để người dùng bỏ qua bước này nếu muốn (tài liệu ngắn, đa lĩnh
      vực, hoặc muốn tự viết prompt qua Phase B).
- **Acceptance:** thuật ngữ dịch cho cùng một khái niệm nhất quán xuyên suốt
  tài liệu dài nhiều trang khi dùng engine LLM (so sánh trước/sau khi bật
  tính năng trên tài liệu 06/07 trong `test_samples/`).

---

## Phase D — Preview theo trang trong GUI desktop (độc lập, có thể song song B/C)

Đọc trước: `pdf2zh/high_level.py` (callback tiến độ theo trang, khu vực dùng
`tqdm.tqdm` + `callback(progress)`), `app/gui.py` (khu vực "Per-page progress
inside the file being translated").

- [ ] **Không** ghi file PDF từng phần ra đĩa trong lúc dịch — rủi ro trùng
      đúng vùng đã có lỗi lịch sử (tài liệu bị nhân đôi/nén lại toàn bộ ở
      bước kết thúc, xem `agent-knowledge/regressions.md`).
- [ ] Thêm khung xem trước (panel) trong `app/gui.py`, cập nhật ảnh render
      từng trang ngay khi trang đó dịch xong, tái dùng callback tiến độ theo
      trang đã có sẵn — không xây cơ chế tiến độ mới từ đầu.
- [ ] Người dùng cuộn xem được các trang đã xong trong khi các trang còn lại
      tiếp tục dịch nền; file PDF thật chỉ xuất hiện khi toàn bộ tài liệu
      dịch xong (giữ nguyên hành vi serialize-một-lần-ở-cuối hiện tại).
- **Acceptance:** dịch 1 tài liệu nhiều trang, mở panel preview, thấy trang 1
  hiển thị trước khi trang cuối dịch xong; không có file PDF từng phần nào bị
  ghi ra đĩa cho tới khi hoàn tất.

**Verify:** `.\.venv\Scripts\python.exe app\gui.py --smoke-test` (theo gate ở
[`agent-knowledge/validation.md`](../agent-knowledge/validation.md)).

---

## Câu hỏi còn mở

- Phase C: cần glossary tĩnh bổ sung cho lĩnh vực đặc biệt (y khoa, luật) hay
  nhận diện lĩnh vực + prompt động là đủ? — để ngỏ, quyết định khi làm Phase C.
- Phase B: hỗ trợ những nhà cung cấp LLM cụ thể nào trước (OpenAI trước,
  Claude/Gemini/DeepSeek sau vì đều tương thích chuẩn OpenAI-compatible)? — để
  ngỏ, có thể quyết định khi bắt đầu code Phase B.
