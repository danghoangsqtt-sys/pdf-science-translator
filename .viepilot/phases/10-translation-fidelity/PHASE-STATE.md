# Phase 10 — translation-fidelity

- Status: technical_verified
- Source requests: BUG-020, BUG-021, BUG-022 (brainstorm `docs/brainstorm/session-2026-11-12.md`)
- Technical gate: passed 2026-11-12 (436/436 unittest, Ruff lỗi cứng, gate PDF thật — trừ BUG-023)
- Version target: 0.4.0 (không đổi).
- Execution root: `D:/DataAdmin/vp-pdf` trên `release/0.4.0` / `main` (`ec235f6`, đã gộp cả dọn mã `15381d6` và BUG-023 `ec235f6`).
- Git persistence: pushed to `origin/main` and `origin/release/0.4.0` (`ec235f6`); no release tag yet.

| Task | Status | Verification |
| --- | --- | --- |
| P10-T1 | technical_verified | `test_formula_line_preserved` 8/8; trang 2: mệnh đề DE giữ nguyên từng ký tự, 16/16 glyph toán |
| P10-T2 | technical_verified | `test_preservation_rules` +3; trang 6: 23 dòng văn xuôi tiếng Việt, 26/26 mục giữ nguyên dạng sắp chữ |
| P10-T3 | technical_verified | `test_heading_room` 9/9; tiêu đề III/IV/V/C 9,96 = gốc; References 7,97, tiêu đề Bảng I 7,27 (≥ small caps gốc) |
| P10-T4 | technical_verified | Gate `_workspace/output/p10/2307.15299v5-vi.pdf` (translategemma:12b): mọi kiểm Phase 10 đạt; số bị model đổi cách viết (trang 1, 4) có cả trước Phase 10 → BUG-023 |

Chưa kiểm tay trong ứng dụng Electron; chưa gắn tag/phát hành Release.
