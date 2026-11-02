---
name: pdf-translate
description: Dịch tài liệu PDF (bao gồm scan an toàn) sang tiếng Việt hoặc 35 ngôn ngữ Latin khác, bảo toàn bố cục, công thức, bảng và hình ảnh. Sử dụng Code4Life / VI-Translate engine.
license: AGPL-3.0-only
---

# PDF Translate Skill (Antigravity & ViePilot)

Translate local PDFs with the bundled Code4Life engine (`VI-Translate`). Keep the source file unchanged and produce a separate PDF with the same page structure.

## Skill Root
The repository root `d:\DataAdmin\vp-pdf` contains the engine core:
- Core: `d:\DataAdmin\vp-pdf\pdf2zh`
- Scripts: `d:\DataAdmin\vp-pdf\scripts\translate_pdf.py`
- Python Virtualenv: `d:\DataAdmin\vp-pdf\.venv\Scripts\python.exe`
- Knowledge: `d:\DataAdmin\vp-pdf\agent-knowledge\index.md`

## Modes

| Mode | Engine | Use case |
| --- | --- | --- |
| **Google (Mặc định)** | `translate.google.com` | Sách, batch nhiều tài liệu, tài liệu thông thường |
| **Handoff** | Active AI Agent | Tài liệu chuyên ngành, cần thuật ngữ chính xác cao hoặc bảo mật |

## Command Syntax (Windows)

```powershell
# 1. Dịch tài liệu PDF cơ bản bằng Google Translate (Mặc định tiếng Việt):
& "d:\DataAdmin\vp-pdf\.venv\Scripts\python.exe" "d:\DataAdmin\vp-pdf\scripts\translate_pdf.py" "path\to\document.pdf" --output-dir "path\to\output"

# 2. Dịch với trang chỉ định (ví dụ trang 1 đến 5):
& "d:\DataAdmin\vp-pdf\.venv\Scripts\python.exe" "d:\DataAdmin\vp-pdf\scripts\translate_pdf.py" "path\to\document.pdf" --pages 1-5 --output-dir "path\to\output"

# 3. Chế độ OCR cho tài liệu scan (nếu đã cài requirements-ocr):
& "d:\DataAdmin\vp-pdf\.venv\Scripts\python.exe" "d:\DataAdmin\vp-pdf\scripts\translate_pdf.py" "path\to\document.pdf" --ocr standard --output-dir "path\to\output"
```
