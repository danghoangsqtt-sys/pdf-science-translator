# Hướng dẫn cài đặt — PDF Translate (vp-pdf)

Tài liệu này dành cho việc chạy và kiểm thử từ mã nguồn trên máy Windows hiện
tại. Không sửa đổi bất kỳ file mã nguồn nào trong `pdf2zh/`, `app/`, `scripts/`.

## 1. Yêu cầu hệ thống

- Windows 10/11 x64
- Python 3.11 (khớp với `.venv` đã có trong repo, tạo bằng Python 3.11.9)
- ~1.5 GB dung lượng trống (model layout OCR + font Unicode + dependencies)
- Kết nối Internet khi dùng engine dịch Google (không cần Internet khi chỉ chạy OCR cục bộ)

## 2. Cài đặt từ đầu (máy sạch)

```powershell
git clone https://github.com/danghoangsqtt-sys/Vp_translator.git
cd Vp_translator
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt        # core dịch + OCR
.\.venv\Scripts\python.exe -m pip install -r requirements-app.txt    # thêm GUI desktop
.\.venv\Scripts\python.exe scripts\fetch_assets.py                   # tải model layout + font Unicode
```

`fetch_assets.py` tải `doclayout.onnx` (~75 MB) và font `GoNotoKurrent-Regular.ttf`
(~15 MB) vào `app/assets/`. Không có bước này, engine layout sẽ báo thiếu model.

## 3. Xác minh cài đặt (trạng thái hiện tại trên máy này)

Repo này (`D:\DataAdmin\vp-pdf`) đã ở trạng thái sẵn sàng:

- `.venv/` đã tạo, dependencies đã cài đủ.
- `app/assets/` đã có model layout + font (theo brainstorm session 2026-09-10).
- Bộ test hồi quy: 278/278 `unittest` OK (ghi nhận trong session trước).

Kiểm tra lại nhanh (không sửa code, chỉ chạy):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

## 4. Chạy dịch một file PDF (dòng lệnh)

```powershell
# Dịch bằng Google (mặc định, cần Internet, không cần API key)
.\.venv\Scripts\python.exe scripts\translate_pdf.py "INPUT.pdf" --output-dir "OUT"

# Giới hạn số trang (dịch nhanh để thử nghiệm)
.\.venv\Scripts\python.exe scripts\translate_pdf.py "INPUT.pdf" --pages 1-5 --output-dir "OUT"

# Bật OCR cho trang scan (standard | enhanced)
.\.venv\Scripts\python.exe scripts\translate_pdf.py "INPUT.pdf" --ocr standard --output-dir "OUT"

# Dịch bằng Handoff (AI agent dịch theo ngữ cảnh, không gửi dữ liệu ra Google)
.\.venv\Scripts\python.exe scripts\translate_pdf.py "INPUT.pdf" --engine handoff --emit-segments segments.jsonl
# ... agent dịch segments.jsonl -> translations.jsonl ...
.\.venv\Scripts\python.exe scripts\translate_pdf.py "INPUT.pdf" --engine handoff --segments translations.jsonl --output-dir "OUT"
```

Các cờ CLI đầy đủ (từ `scripts/translate_pdf.py --help`):

| Cờ | Ý nghĩa |
| --- | --- |
| `--output-dir` | Thư mục lưu PDF đã dịch |
| `--target-language` / `--source-language` | Ngôn ngữ đích/nguồn (mặc định tiếng Việt) |
| `--pages` | Giới hạn trang, vd `1-5` |
| `--threads` | Số luồng xử lý song song |
| `--engine` | `google` (mặc định) hoặc `handoff` |
| `--ocr` | `off` (mặc định) / `standard` / `enhanced` |
| `--segments` / `--emit-segments` | Vào/ra JSONL cho chế độ Handoff |
| `--ignore-cache` | Bỏ qua cache bản dịch |
| `--overwrite` | Ghi đè file đã dịch trước đó |

## 5. Chạy giao diện Desktop (GUI)

```powershell
.\.venv\Scripts\python.exe app\gui.py
```

Kéo-thả file/thư mục PDF vào cửa sổ; kết quả lưu vào thư mục `translated`
cạnh file nguồn.

## 6. Build gói cài đặt (không cần cho việc kiểm thử chất lượng/tốc độ)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Tạo `dist\PDFTranslate-windows.zip`. Bỏ qua bước này nếu mục tiêu chỉ là đo
tốc độ/chất lượng dịch qua CLI hoặc GUI chạy trực tiếp từ `.venv`.

## 7. Giới hạn cần biết trước khi kiểm thử

- Mỗi đoạn gửi tới Google giới hạn 5.000 ký tự; phần vượt quá không được dịch.
- Hỗ trợ 36 ngôn ngữ dùng chữ Latin; không hỗ trợ Trung/Nhật/Hàn/Ả Rập/Thái/chữ Ấn Độ.
- OCR mặc định tắt (`--ocr off`); bật `standard`/`enhanced` chỉ cho trang scan.
- Bảng/công thức/vùng nhận dạng không chắc chắn được giữ nguyên → tài liệu có
  thể được báo là "dịch một phần" (partial), đây là hành vi đúng theo thiết kế,
  không phải lỗi.
- **Số trang khuyến nghị:** đã kiểm chứng sạch tới 36 trang (bài báo/chương
  ngắn) trong benchmark thật. Tài liệu trên 50 trang (`PAGE_COUNT_ADVISORY_LIMIT`
  trong `scripts/translate_pdf.py`) vẫn dịch được — đây không phải giới hạn
  cứng — nhưng CLI/GUI sẽ tự hiện thông báo khuyên nên dịch thử một khoảng
  trang bằng `--pages` trước, rồi mới dịch cả tài liệu, và kiểm tra kỹ các
  trang nhiều công thức/bảng trong kết quả trước khi dùng cho việc quan trọng.
