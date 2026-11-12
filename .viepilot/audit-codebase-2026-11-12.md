# VP-AUDIT — Vệ sinh mã nguồn và bố cục, `release/0.4.0`, 12/11/2026

Phạm vi: dọn mã chết, tệp thừa, bố cục và tài liệu lệch. Báo cáo này nối tiếp
`audit-codebase-2026-11-09.md` (nhánh Phase 9), không lặp lại các lỗi vận hành
đã ghi ở đó (BUG-014..018, ENH-003).

Cơ sở: worktree `claude/vp-audit-codebase-cleanup-ba45c1` được đặt lại về
`release/0.4.0` (`30e37d8`) vì nó được cắt từ nhánh cũ
`fix/pipeline-crash-and-text-corruption` (bố cục Tkinter). Chưa sửa mã sản phẩm.

## Bối cảnh nhánh (ảnh hưởng quyết định dọn)

| Nhánh | Trạng thái |
| --- | --- |
| `release/0.4.0` | Sản phẩm hiện hành; **4 commit chưa push** lên `origin`. |
| `claude/evolve-progress-fixes-responsive-ui` | **7 commit chưa merge** (Phase 8–9, figure labels): 60 tệp, gồm `frontend/src/components`, `backend/pdf2zh`, `agent-knowledge`, `CHANGELOG.md`. Đã sửa BUG-014/015/017. |
| 15 nhánh local khác | Đã merge hết vào `release/0.4.0` (main, fix/pipeline…, feature/offline-engine, backup/*, claude/*). 5 worktree trỏ vào chúng. |

→ Mọi thay đổi bố cục trên `release/0.4.0` sẽ xung đột với Phase 9. Nên merge
Phase 9 trước hoặc cắt nhánh dọn từ đỉnh Phase 9.

## Kiểm chứng

- `backend`: 394 test, **392 đạt, 2 lỗi** — `test_inline_formula_layout.py:554,562`
  mở cứng `app/assets/GoNotoKurrent-Regular.ttf` (tệp gitignore) và không `skipUnless`
  như các test asset khác → hỏng trên mọi bản clone/worktree mới.
- Ruff mở rộng (F/B/ERA/PLW): mã sản phẩm sạch; chỉ vài điểm nhỏ (dưới).
- Frontend: không còn `node_modules` trong worktree nên chưa chạy lại `tsc`
  (lượt 09/11 đạt).

## Tier 1 — Trạng thái ViePilot (trên `release/0.4.0`)

| Kiểm tra | Kết quả |
| --- | --- |
| HANDOFF.json | ⚠️ Vẫn ghi `feature/offline-engine`, worktree `frosty-ritchie-f4e306`, next P6-T1 (đã có BUG-018 trên nhánh Phase 9). |
| PHASE-STATE 01-offline/02-interface/03-delivery | ⚠️ `in_progress` dù đã giao. |
| Tag `vp-p*-complete` | ℹ️ Không có; chủ đích. |

## Tier 2 — Tài liệu lệch bố cục

| # | Vị trí | Vấn đề |
| --- | --- | --- |
| D1 | `agent-knowledge/release.md:3,14`, `repository.md:9,12-17,40` | Vẫn mô tả `webui/` và `app/errors.py` ở gốc; mâu thuẫn với mục "Folder Layout" cuối cùng tệp. |
| D2 | `docs/kien-truc/codebase-architecture.md:12,35` | Sơ đồ kiến trúc vẫn có "Desktop Tkinter" và `app/` cũ; `repository.md` dẫn tới tệp này như bản đồ chuẩn. |
| D3 | `docs/huong-dan/installation-guide.md:4`, `frontend/src/services/api.ts:86` | Trỏ `webui/`. |
| D4 | `AGENTS.md:21` | Quy tắc "APP_VERSION khớp tag `v*`" trong khi `APP_VERSION` đã bị xóa cùng Tkinter. |
| D5 | `frontend/package.json` | `version: 1.0.0`, `author: Code4Life`, mô tả "Minimal…" — lệch sản phẩm 0.4.0 / DHsystem. |

## Tier 3 — Vệ sinh mã và bố cục

| # | Mức | Phát hiện | Vị trí | Đề xuất |
| --- | --- | --- | --- | --- |
| H1 | medium | **Mã chết từ Tkinter**: `app/errors.py` (mã lỗi E-PDF-0x, báo cáo copy) không còn ai import ngoài chính test của nó (11 test). Server/Electron dùng mã lỗi riêng. | `backend/app/errors.py`, `backend/tests/test_app_errors.py`, chú thích `scripts/translate_pdf.py:639` | Xóa cả hai; sửa chú thích. |
| H2 | medium | **Tên thư mục sai nghĩa**: `backend/app/` giờ chỉ chứa asset/font, không còn "app". Đường dẫn này nằm trong bản đóng gói (`resources/backend/app/assets`), `ocr.py:33`, 3 script build, 3 test, `package.json`. | `backend/app/` | Tùy chọn: đổi thành `backend/assets/` (+`fonts/`). **Rủi ro**: phá cập nhật tại chỗ cho 2 bản trong `BAN-CAI-DAT` → chỉ làm khi build lại. |
| H3 | medium | **Cấu hình cá nhân bị commit**: `.codex/config.toml` chứa đường dẫn `C:\Users\Admin\AppData\...` của máy này. | `.codex/config.toml` | Bỏ khỏi git, thêm vào `.gitignore`. |
| H4 | medium | **Ba bản skill `pdf-translate` lệch nhau**: gốc `SKILL.md` (142 dòng, chuẩn), `.claude/skills/` (adapter mỏng, đúng), `.agents/skills/` (36 dòng, viết lại riêng, cứng `d:\DataAdmin\vp-pdf`, nhãn "Code4Life"). Ngoài ra 22 skill `vp-*` cài bởi ViePilot được commit trong `.agents/skills/` (320 KB). | `.agents/skills/` | Đổi `.agents/.../pdf-translate` thành adapter mỏng như bản Claude; gỡ 22 skill `vp-*` khỏi git (cài lại bằng `vp-tools install`). |
| H5 | low | Test phụ thuộc asset không skip (xem Kiểm chứng). | `tests/test_inline_formula_layout.py:554,562` | `skipUnless(asset.exists())`. |
| H6 | low | Smoke test bản portable vẫn `import tkinter` — thừa sau khi bỏ Tkinter; sẽ chặn build nếu runtime nhúng bỏ tkinter. | `scripts/build_offline_windows.py:151` | Bỏ `tkinter` khỏi lệnh import. |
| H7 | low | Ảnh trùng lặp: `frontend/icon.png` == `frontend/public/icon.png` (844 KB mỗi bản, cùng MD5). | `frontend/` | Cho electron-builder trỏ `public/icon.png`, xóa bản gốc; cân nhắc nén icon. |
| H8 | low | Dependency build-time nằm trong `dependencies` (`autoprefixer`, `postcss`, `tailwindcss`); mọi thư viện renderer đã được Vite bundle nên electron-builder đóng gói thừa vào `node_modules` của asar. | `frontend/package.json` | Chuyển sang `devDependencies`; đo lại cỡ installer. |
| H9 | low | Bằng chứng sinh máy được commit: `docs/bao-cao/bang-chung/**/*.json` (~700 KB dump hash), `legacy-scratch-tools.zip`, `.viepilot/audit-evidence-2026-10-29/*.log`, `planning-evidence/source-before.json`. | `docs/bao-cao/bang-chung/`, `.viepilot/` | Giữ (quy ước "không sửa bằng chứng"), nhưng không commit thêm dump mới; ghi rõ quy ước trong `docs/README.md`. Không viết lại lịch sử. |
| H10 | low | Lint nhỏ trong mã của dự án: import thừa `Sequence` (`pdf2zh/converter.py:7`), `socket` (`tests/test_offline.py:5`); `raise` không `from` (`server/main.py:210`). Phần ERA001/B006 trong `pdfinterp.py` là mã upstream pdfminer → để nguyên. | như cột trái | `ruff --fix` đúng 2 import; thêm `from exc`. |
| H11 | low | Service chưa nối: `engine_service`, `device_check_service`, `hardware_service` (= ENH-003, đã có). Tên `EnginePicker.tsx` giờ chọn *profile*. | `backend/server/services/`, `frontend/src/components/` | Theo ENH-003; đổi tên `ProfilePicker`. |
| H12 | info | Hai đường đóng gói song song: `package.json > build` (electron-builder, không có `offline-data`) và `scripts/build_offline_windows.py` (bản portable đang phát hành). | | Ghi rõ đường nào là chuẩn trong `release.md`. |

### Dọn local (ngoài git, cần đồng ý)

- 15 nhánh local đã merge và 5 worktree cũ (xem bảng nhánh). `backup/*` nên giữ
  đến khi push `release/0.4.0`.
- Dung lượng thư mục: xem phụ lục.

## Guardrails cho `vp-auto`

- Không thêm module mới vào `backend/app/`; asset mới đi cùng tên thư mục chuẩn đã chọn.
- Test cần tệp gitignore phải `skipUnless` tệp tồn tại.
- Không commit cấu hình máy (`.codex/`, `settings.local.json`, đường dẫn tuyệt đối).
- Adapter skill chỉ trỏ về `SKILL.md` gốc, không sao chép nội dung.
- Thay đổi bố cục phải cập nhật cùng lúc: `package.json extraResources`,
  `build_offline_windows.py`, `prepare_offline_pack.py`, `agent-knowledge/repository.md`.

## Phụ lục — dung lượng `D:\DataAdmin\vp-pdf` (12/11/2026)

| Thư mục | MB | Nhận xét |
| --- | ---: | --- |
| `BAN-CAI-DAT` | 29.099 | 2 bản portable (đầy đủ + nhẹ); đúng chủ đích. |
| `BAN-CHAY` | 1.545 | venv + python_runtime. |
| `frontend` | 639 | Chủ yếu `node_modules`/bản build; không có trong git. |
| `.claude` | 208 | 5 worktree đã merge có thể dọn. |
| `backend` | 159 | model layout + font (gitignore). |
| `_workspace` | 137 | mẫu/scratch/backup. |
| `.git` | 20 | Nhỏ; không cần viết lại lịch sử. |

Không có pack trung gian 26 GB còn sót lại; không có thư mục cấm (`tmp/`, `output/`, `test_*`) ở gốc.

## Backlog đề xuất (ID tiếp sau nhánh Phase 9)

- BUG-019 — test asset không skip + smoke `tkinter` (H5, H6)
- ENH-008 — gỡ mã chết `app/errors.py` và lint nhỏ (H1, H10)
- ENH-009 — vệ sinh repo: `.codex/`, `.agents/skills`, icon trùng, deps (H3, H4, H7, H8)
- ENH-010 — đổi `backend/app/` → `backend/assets/` khi build lại bản cài (H2)
- Re-detected vào BUG-018: D1–D5.
