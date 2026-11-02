# Báo cáo kiểm thử: tốc độ & chất lượng dịch (2026-09-10)

- **Phạm vi:** đo tốc độ và chất lượng dịch qua CLI có sẵn
  (`scripts/translate_pdf.py`), engine **Google** (mặc định, không API key).
- **Không sửa mã nguồn:** toàn bộ kết quả dưới đây thu được bằng cách gọi CLI
  hiện có và đọc/đo file PDF đầu ra bằng PyMuPDF. Không có file nào trong
  `pdf2zh/`, `app/`, `scripts/` bị chỉnh sửa.
- **Máy đo:** `D:\DataAdmin\vp-pdf`, Python 3.11.9, `.venv` sẵn có, 4 threads
  (mặc định), OCR tắt (các file test đều là PDF văn bản, không phải scan).
- **Bộ tài liệu:** 4 bài báo khoa học mở (arXiv, tải qua
  `export.arxiv.org`/`arxiv.org/pdf`), chọn theo 4 mức dung lượng/số trang.

## 1. Bộ tài liệu kiểm thử

| # | File | Nguồn arXiv | Trang | Dung lượng | Đặc điểm |
| --- | --- | --- | --- | --- | --- |
| Nhỏ | `05_arxiv_small_mond.pdf` | 2609.07503 | 8 | 310 KB | Vật lý lý thuyết, nhiều công thức inline |
| Vừa | `06_arxiv_medium_cosmology.pdf` | 2609.09045 | 22 | 547 KB | Vũ trụ học, 6 bảng + hệ phương trình |
| Lớn | `07_arxiv_large_datacenters.pdf` | 2608.27517 | 36 | 419 KB | Kỹ thuật, 20 bảng, nhiều công thức ma trận |
| Rất lớn | `08_arxiv_xlarge_llm_survey.pdf` | 2303.18223 | 144 | 5.37 MB | Bài khảo sát dài, dày đặc bảng/tham chiếu |

File gốc lưu tại `test_samples/`, không sửa/không ghi đè. File dịch nằm ở
`test_output/benchmark/`.

## 2. Tốc độ dịch (Google engine, 4 threads)

| Tài liệu | Trang | Thời gian | Giây/trang | Kết quả |
| --- | --- | --- | --- | --- |
| Nhỏ (8tr) | 8 | 31.2 s | 3.9 | ✅ Hoàn tất |
| Vừa (22tr) | 22 | 11.2 s | 0.51 | ✅ Hoàn tất |
| Lớn (36tr) | 36 | 79.3 s | 2.2 | ✅ Hoàn tất |
| Rất lớn (144tr) | 144 | crash ở ~59 s (giữa trang 17/144) | — | ❌ **Không ra file** |

Tốc độ mỗi trang dao động 0.5–4 giây, phụ thuộc mật độ công thức/bảng và độ
trễ mạng lúc gọi Google Translate (đo lúc 2026-09-10) hơn là dung lượng file
tính bằng MB — file lớn nhất về trang (144tr) lại crash trước khi có số liệu
tốc độ đầy đủ; trong số 3 file hoàn tất, file "Lớn" 36 trang nhưng nhiều bảng
lại tốn 2.2 s/trang, chậm hơn file 22 trang.

Tái xác nhận (`--pages`): dịch trang 1–20 và 15–20 của tài liệu 144 trang đều
**thành công** trong vài giây — nghĩa là không có trang đơn lẻ nào tự nó gây
lỗi; sự cố chỉ hiện ra khi xử lý toàn bộ 144 trang liền mạch (chi tiết ở mục 4).

## 3. Chất lượng dịch — quan sát trực quan

Đối chiếu ảnh render 150dpi trang nguồn và trang dịch (theo quy trình PDF Gate
ở [`agent-knowledge/validation.md`](../agent-knowledge/validation.md)):

- **Công thức toán (05, trang 4 — pt. 9):** giữ nguyên 100% glyph, vị trí, cỡ
  chữ. Văn xuôi xung quanh dịch tự nhiên, đúng ngữ cảnh MOND/vật lý thiên văn.
- **Hệ phương trình + chứng minh (06, trang 6 — pt. 26–31):** toàn bộ công
  thức, ký hiệu (Proposition/Remark, chỉ số dưới, superscript) giữ nguyên;
  tiêu đề mục dịch đúng ("Detection basis..." → "Cơ sở phát hiện...").
- **Văn bản kỹ thuật dày đặc công thức (07, trang 23 — pt. 60):** công thức
  Maxwell reciprocity giữ nguyên, nhưng phát hiện **lỗi thật** — xem mục 4.

## 4. Các phát hiện chất lượng (theo mức độ nghiêm trọng)

### 4.1 Nghiêm trọng — Crash toàn bộ, không tạo được file dịch (tài liệu 144 trang)

```
error: PDF translation core failed: PDFValueError: Failed to translate
D:\DataAdmin\vp-pdf\test_samples\08_arxiv_xlarge_llm_survey.pdf <- KeyError: 'N'
```

- Xảy ra ổn định khi dịch **toàn bộ** file 144 trang (đã thử lại, lỗi lặp lại
  ở cùng vị trí tiến trình ~17/144).
- **Không** tái hiện khi dịch cùng nội dung qua `--pages 1-20` hoặc
  `--pages 15-20` — cả hai đều hoàn tất bình thường. Điều này gợi ý lỗi liên
  quan đến trạng thái/bộ đếm tích lũy qua toàn văn bản (không phải nội dung
  một trang đơn lẻ) chứ không phải một trang "hỏng" cụ thể.
- 144 trang / 5.37 MB vẫn nằm trong ngưỡng "tài liệu lớn" mà sản phẩm tự nhận
  hỗ trợ (200 trang / 50 MiB, theo `agent-knowledge/pdf-engine.md`), nên đây
  không phải trường hợp vượt ngoài phạm vi công bố.
- Ngay trước khi crash, log còn ghi `style tags are not closed` và một đoạn bị
  `FormulaPlaceholderError` — có thể liên quan đến cùng chuỗi sự kiện.
- **Tác động:** người dùng dịch một bài khảo sát khoa học dài (rất phổ biến
  trên arXiv) bằng app sẽ nhận lỗi và không có file đầu ra nào, dù tài liệu
  nằm trong giới hạn được quảng cáo.

### 4.2 Trung bình — Văn bản lai hỏng, không được cảnh báo (tài liệu 36 trang, trang 23)

Trích xuất văn bản thật từ PDF đã dịch:

```
thiết lập sự tương ứng
onding Maxmối quan hệ có đi có lại tốt trong
công thức cấu thành hiện tại.
```

- Câu gốc: "...which establishes the **corresponding Max**well reciprocity
  relation within the present constitutive formulation."
- Đoạn `"onding Max"` (mảnh vỡ tiếng Anh của "corresponding Max[well]") bị kẹt
  giữa hai cụm tiếng Việt — rõ ràng là lỗi ghép/tràn văn bản khi dựng lại
  trang, không phải do Google dịch sai nghĩa.
- **Đáng lưu ý:** công cụ không phát ra warning nào cho đoạn này (không nằm
  trong danh sách "left in source language"/"partial") — tức là gate nội bộ
  hiện tại không bắt được kiểu hỏng này, và tài liệu vẫn được báo là dịch
  thành công hoàn toàn.

### 4.3 Thấp — Thiếu khoảng trắng trước biến số công thức inline (tài liệu 8 trang)

Nhiều chỗ trong văn xuôi tiếng Việt bị dính liền vào ký hiệu toán học theo
sau, ví dụ: `"chúng ta thấyA0chỉ phụ thuộc"`, `"phụ thuộc vàoM và λ"`,
`"mối quan hệ giữaA0vàM"`. Không làm sai nghĩa hay hỏng bố cục, nhưng ảnh
hưởng khả năng đọc. Nhất quán ở nhiều vị trí trong cùng tài liệu.

### 4.4 Không phải lỗi — nhiễu dương tính giả khi quét ký tự rác

Theo gate ở `validation.md` (tìm `U+0000`/`U+FFFD` trong văn bản trích xuất),
việc quét thô trên **văn bản đầu ra** báo "leak" ở nhiều trang (05 tr.4; 06
tr.4,7,9,11,15,18; 07 tr.20,30). Đối chiếu với **văn bản nguồn cùng trang**
thì các ký tự `\x00`/`\x01` này **đã có sẵn trong PDF gốc**, xung quanh dấu
ngoặc lớn của công thức (font mở rộng LaTeX không có ToUnicode cho glyph dấu
ngoặc kéo dài). Công cụ giữ nguyên byte-for-byte đúng theo thiết kế bảo toàn
công thức — đây là **bằng chứng bảo toàn đúng**, không phải lỗi rò rỉ
placeholder. Rút kinh nghiệm quy trình: gate cần so **nguồn và đích cùng
trang** thay vì chỉ quét đầu ra, để tránh báo động giả.

### 4.5 Hành vi đúng theo thiết kế — dịch một phần khi không đủ chỗ

`06`: 8 đoạn, `07`: 1 đoạn bị giữ nguyên tiếng Anh vì "single line needs less
than 50% font size" — đúng theo bất biến bảo toàn đã ghi trong
`agent-knowledge/pdf-engine.md` (không co chữ dưới 50% cỡ gốc). Không tính là
lỗi.

## 5. Khuyến nghị

1. **Ưu tiên cao:** điều tra crash `KeyError: 'N'` trên tài liệu dài xử lý
   toàn văn bản (mục 4.1) — chặn hoàn toàn việc dịch các bài khảo sát khoa
   học dài, một nhóm tài liệu người dùng mục tiêu rất hay gặp.
2. **Ưu tiên trung bình:** rà lại gate phát hiện lỗi dựng trang để bắt được
   kiểu văn bản lai hỏng như mục 4.2 — hiện tại lỗi này "lọt lưới" và được
   báo cáo là thành công.
3. **Ưu tiên thấp:** thêm khoảng trắng khi chèn biến công thức inline ngay
   sau từ tiếng Việt không có dấu cách (mục 4.3).
4. Theo quy trình chuẩn của repo, đây là báo cáo phát hiện — việc sửa (nếu
   có) nên đi qua `/vp-request` → `/vp-evolve`, không sửa trực tiếp ở đây.

## 6. Cách tái hiện

```powershell
# Trung bình/nhỏ (thành công)
.\.venv\Scripts\python.exe scripts\translate_pdf.py test_samples\07_arxiv_large_datacenters.pdf --output-dir test_output\benchmark --overwrite

# Rất lớn (crash toàn bộ)
.\.venv\Scripts\python.exe scripts\translate_pdf.py test_samples\08_arxiv_xlarge_llm_survey.pdf --output-dir test_output\benchmark --overwrite

# Cùng nội dung nhưng theo đoạn nhỏ (không crash)
.\.venv\Scripts\python.exe scripts\translate_pdf.py test_samples\08_arxiv_xlarge_llm_survey.pdf --pages 1-20 --output-dir test_output\benchmark --overwrite
```
