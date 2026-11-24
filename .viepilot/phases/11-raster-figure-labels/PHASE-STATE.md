# Phase 11 — raster-figure-labels

- Status: technical_verified
- Source request: ENH-011 (brainstorm `docs/brainstorm/session-2026-11-12.md`, E3/D1/D4)
- Technical gate: passed 2026-11-24 (462/462 unittest, pip check, Ruff lỗi cứng, gate PDF thật 2307.15299v5 + scan OCR)
- Git persistence: committed and pushed to `origin/release/0.4.0` and `origin/main` (2026-11-24); no release tag yet.
- Version target: 0.4.0 (không bump; nguồn phiên bản `frontend/package.json`)
- Execution root: `D:/DataAdmin/vp-pdf` trên nhánh `release/0.4.0` (bố cục `backend/` + `frontend/`)

| Task | Status | Verification |
| --- | --- | --- |
| P11-T1 | technical_verified | `test_figure_ocr_eligibility` 8/8 (gồm chú giải có vạch màu) + `test_figure_labels` 18/18; Ruff 0 lỗi |
| P11-T2 | technical_verified | `test_figure_ocr_render` 3/3 + `test_number_fidelity` 9/9; Ruff 0 lỗi |
| P11-T3 | technical_verified | `test_figure_ocr_pipeline` 6/6 + full suite 462/462; `pip check` + Ruff 0 lỗi |
| P11-T4 | technical_verified | `2307.15299v5-vi.pdf`: 114/114 đoạn, 246/246 glyph toán, 69 nhãn ảnh phủ sạch (đã xem render tr.2–5); `04_scanned_book_page-vi.pdf` (`--ocr standard`): 3/3 đoạn, không hồi quy |

Không ghi `technical_verified` hoặc `PASS` chỉ vì kế hoạch đã được tạo.
