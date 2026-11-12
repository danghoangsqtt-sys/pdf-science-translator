# Phase 10 — Summary (12/11/2026)

Bài kiểm: arXiv 2307.15299v5 (6 trang, IEEE hai cột), translategemma:12b, dev venv.
Bản dịch: `_workspace/output/p10/2307.15299v5-vi.pdf`. Bản cũ của người dùng không bị ghi đè.

| Lỗi | Trước | Sau |
| --- | --- | --- |
| BUG-020 công thức | `f(s) ≤ f(x)` → `s, ≤ f, x`; `f(s) ≠ −∞` → "f là s và ≠ −∞" | Dòng mệnh đề giữ nguyên từng ký tự; `f(s)` giữa câu là một marker |
| BUG-021 trang 6 | Cả trang tiếng Anh | Kết luận + lời cảm ơn tiếng Việt; danh mục 26 mục giữ nguyên dạng sắp chữ |
| BUG-022 tiêu đề | III. 6,06 pt, C. 7,03, tiêu đề bảng 5,91, References 5,3 | III/IV/V/C 9,96 (= gốc), References 7,97, tiêu đề bảng 7,27 |

## Thay đổi mã
- `pdf2zh/converter.py`: `attaches_to_formula`, `looks_like_formula_line` trong `is_translatable_segment`, `single_line_room`, `glyph_line_boxes`.
- `pdf2zh/rules.py`: `looks_like_formula_line`, `prose_precedes_references`, `bibliography_rects`.
- `pdf2zh/high_level.py`: trang trộn tham khảo — bảo vệ vùng danh mục thay vì cả trang.
- Test mới: `test_formula_line_preserved.py`, `test_heading_room.py`; +3 ca trong `test_preservation_rules.py`. Suite 436/436.

## Phát hiện ngoài phạm vi
- BUG-023: model đổi cách viết số trong văn xuôi (96,432 → 96.432; 3D/2D → "ba/hai chiều"; mất "1st").
- Thuật ngữ nhãn Fig. 2: "Current Population" → "Dân số hiện tại", "Fitness" → "thể lực" (nên là quần thể / độ thích nghi) — glossary.
- Đoạn ngay sau dòng công thức trang 2 vẫn co chữ (E5 trong brainstorm, chưa lên lịch).
- Android không hưởng các sửa này (pipeline riêng).
