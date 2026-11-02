# Audit dọn dẹp an toàn và cấu hình laptop — 28/10/2026

Đã dọn đúng danh sách được đối chiếu, không xóa mã nguồn sản phẩm hay model gốc.
Người dùng xác nhận ứng dụng hiện chạy tốt; lần audit này tập trung dọn kết quả
cũ và đánh giá khả năng áp dụng laptop, không thay đổi thuật toán dịch.

## Kết quả dọn

| Mục | Xử lý | Bằng chứng giữ lại |
| --- | --- | --- |
| Gói trung gian `build/offline-data-2026-10-28` trong checkout ngoại tuyến | Xóa 1.022 file, 21.307.739.172 byte | 1.017 tài nguyên bắt buộc khớp SHA-256 với gói portable; các blob model cũng khớp kho gốc. Metadata nhỏ lưu lại, graph tối ưu là cache sinh lại được. |
| 26 script nháp cũ ở `tmp/` của checkout IDE | Đóng ZIP, đối chiếu hash từng thành viên rồi dọn bản rời | `cleanup-evidence-2026-10-28/legacy-scratch-tools.zip` |
| 10 PDF dịch thử cũ ở `test_output/` | Xóa các đầu ra `*-vi.pdf` có nguồn tương ứng còn nguyên | Hash nguồn trong `test_samples/` và hash đầu ra có trong manifest dọn. Báo cáo benchmark lịch sử được giữ. |

Tổng dữ liệu logic đã xóa **21.345.852.541 byte** (khoảng 21,35 GB). Dung lượng
trống ổ D ngay trước/sau thao tác xóa: **42.312.011.776 → 63.660.388.352 byte**.
Trong lần audit cũng phục hồi khoảng 271 MB dependency phát triển bị thiếu;
dung lượng trống thực tế có thể tiếp tục thay đổi theo hoạt động khác của máy.

Giữ nguyên:

- Toàn bộ `app/`, `pdf2zh/`, `scripts/`, `tests/`, frontend/backend, Android và
  thay đổi chưa commit ở cả hai checkout. Các bản nguồn khác nhánh không được
  xem là bản sao có thể xóa chỉ vì tên thư mục giống nhau.
- Kho model gốc `D:/DataAdmin/OllamaModels`, runtime AI cài riêng và mọi model
  trong `build/windows-offline-2026-10-28/resources/offline-data`.
- Bộ portable khoảng 22,66 GB, bằng chứng PDF/ảnh/measurement/QA cuối, PDF nguồn
  trong `docs/`, `test_samples/` và các bản mẫu không xác định chắc là thừa.
- `build/app/xref-app.html` đang mở trong IDE, bộ cài cũ ở `dist/`, dependency
  wheel dự phòng, font/OCR/layout model và tài liệu kiến trúc/xem trước.

Chỉ xóa gói trung gian sau khi xác nhận executable giữ lại, manifest giống nhau,
hash từng bản sao đúng, không có process đang dùng gói trung gian, không có biến
môi trường chỉ vào đó và không có reparse point trên đường dẫn xóa. Thao tác
recursive chỉ áp dụng một đường dẫn tuyệt đối đã kiểm tra; không dùng `git clean`
hay xóa theo phần mở rộng chung trên cả repo.

## Kiểm tra sau dọn

- **500 tệp hiện có được bảo vệ khớp hash**, không tệp nào trong danh sách bị
  xóa/đổi bởi thao tác dọn. Không tính cache graph sinh lại hoặc các báo cáo/metadata
  audit được bổ sung sau bước đối chiếu này.
- Bộ xử lý khởi động từ dữ liệu giữ lại, **ready sau 32,34 giây**, ba profile đều
  sẵn sàng. Không phụ thuộc bản gói trung gian vừa xóa; worker thử đã được dừng.
- Venv Python 3.12: **421/421 unittest** sau dọn, **14,832 giây**; `pip check` và
  Ruff `E9,F63,F7,F82` đạt. Bài native smoke trong suite nạp stack thật.
- Không thay đổi mã renderer hoặc PDF engine. 16 ca Chromium trước đó là bằng
  chứng lịch sử, không ghi thành lượt kiểm tra mới trong lần dọn này.
- Sau dọn đã mở lại và render hai PDF giữ lại: mẫu khoa học mức cao và scan
  một trang. Đã xem ảnh, chữ/công thức/bố cục còn rõ; ảnh ở checkout ngoại tuyến
  `tmp/cleanup-render-qa/`.
- Không commit/push/tag/phát hành. Không đụng ứng dụng, model hay process ngoài
  workspace; không sửa firewall hoặc cấu hình hệ thống.

## Tier 1 — trạng thái và khả năng phục hồi: có vấn đề cần theo dõi

Checkout ngoại tuyến `.claude/worktrees/frosty-ritchie-f4e306` ban đầu thiếu `.git`;
Git báo `prunable` dù thư mục còn nhiều thay đổi. Đã phục hồi đúng file liên kết
theo metadata đăng ký và khóa worktree để tránh prune nhầm. Không reset/checkout
hay ghi đè mã nguồn. Khóa có lý do `Preserve uncommitted offline implementation during cleanup`.

Đồng thời venv thiếu `pyvenv.cfg` và nhiều dependency, nên lượt kiểm thử đầu bị
lỗi import. Đã dựng lại cấu hình trỏ Python 3.12 đang có và **chỉ chép tệp còn
thiếu** từ Python portable cùng phiên bản; không tải mạng hoặc ghi đè dependency
đang tồn tại. Sau đó toàn bộ suite đạt như trên.

**Phát hiện từ trước thao tác xóa:** checkout này có **22 tệp tracked đang thiếu**,
gồm `.gitignore`, requirements, build specs/scripts, README, license/notices và
một số hướng dẫn/workflow. Chúng không bị dọn trong lần này. Chưa tự chép bản
HEAD vào vì có thể làm mất dấu phiên bản chưa commit trước đó. Cần phục hồi và
đối chiếu riêng trước khi coi checkout sẵn sàng dựng/phát hành lại. Ghi `BUG-008`.

Các phase vẫn là kiểm chứng cục bộ/persistence pending; xác nhận chạy tốt trên
desktop hiện tại không thay cho nghiệm thu Windows sạch hoặc laptop.

## Tier 2 — tài liệu: có khác biệt đã ghi rõ

Checkout IDE là nhánh `feat/domain-glossary`, phần triển khai ngoại tuyến ở nhánh
`feature/offline-engine`. Root README và hướng dẫn build của nhánh IDE còn mô tả
luồng cũ; không xóa chúng hoặc gộp hai nhánh khi chưa đối chiếu thay đổi người dùng.
Điểm vào bản hiện tại: [Windows offline](offline-windows-2026-10-28.md).

Một số script đo cũ ghi đường dẫn gói trung gian giờ đã dọn: đó là provenance
của phép đo lịch sử. Để chạy lại, dùng `resources/offline-data` của bộ portable
giữ lại hoặc dựng gói mới từ nguồn local; không sửa lại kết quả đo cũ.
Tài liệu thiết kế Mermaid ở workspace kiến trúc được giữ; không áp đặt cấu trúc
khác lên các quyết định brainstorm đã chốt.

## Tier 3 — stack và tài nguyên: cần nâng cấp để dùng laptop thuận tiện

**ENH-002, mức ưu tiên cao cho đợt laptop:** chưa có phân tích CPU/RAM/VRAM/driver/
ổ trống, context hiện cố định 8.192 token và readiness yêu cầu mọi alias trong
gói đầy đủ. Không thể chỉ xóa model lớn để tạo pack nhẹ. Cần manifest theo profile,
benchmark cục bộ và ngân sách bộ nhớ. Đề xuất cụ thể: [cấu hình laptop](de-xuat-cau-hinh-laptop-2026-10-28.md).

Phần bảo vệ hiện có cần giữ: `UploadFile` đọc giới hạn, token phiên, loopback,
context isolation/sandbox renderer, không `openExternal`, dữ liệu có hash và
cảnh báo bản dịch một phần. Đối chiếu hướng dẫn chính thức
[FastAPI](https://fastapi.tiangolo.com/tutorial/request-files/),
[Electron](https://www.electronjs.org/docs/latest/tutorial/security),
[bộ nhớ/context](https://docs.ollama.com/context-length).

```yaml
stacks: [python, fastapi, react, electron, windows-local-runtime]
summary_used: cache_and_official_documentation
must_follow:
  - Keep offline policy and public profile anonymity unchanged.
  - Preserve source PDFs, uncommitted changes, original model store and valid package.
  - Measure free RAM/VRAM plus driver/runtime compatibility and local benchmark.
  - Validate per-profile resources and full token budget before reducing context.
  - Verify hashes and explicit resolved paths before cleanup; archive unique scratch code.
avoid:
  - Treating build or old worktree folders as disposable without checking contents.
  - Deleting larger models from the current complete-pack manifest.
  - Adding internet downloads, telemetry or silent quality downgrade to offline runtime.
  - Equating weight-file size with total VRAM requirement.
preflight_checklist:
  - Resolve BUG-008 and preserve both branches before changing source layout.
  - Gate ENH-002 on real laptop tests and formula/OCR render QA.
  - Run Python 3.12 unittest, pip check, hard Ruff and proportional UI/PDF verification.
needs_detail_lookup: true
```

## Hồ sơ thao tác

`docs/bao-cao/bang-chung/cleanup-inventory-2026-10-28.json` là kiểm kê trước dọn.
`docs/bao-cao/bang-chung/cleanup-evidence-2026-10-28/` có manifest staging, hash bản sao, danh sách
từng mục xóa, ZIP script, hóa đơn xóa, hash nguồn trước dọn và xác minh sau dọn.
Lệnh kiểm thử và phục hồi dependency ghi ở checkout ngoại tuyến `tmp/cleanup-*`;
công cụ dọn có guard nằm ở checkout IDE `tmp/*cleanup*20261028*`.

Audit ghi hai yêu cầu mới `BUG-008` và `ENH-002`; chưa triển khai tính năng chọn
gói theo máy. Các lỗi thuật ngữ và native startup đã có yêu cầu mở riêng được
giữ nguyên, không biến một lượt suite nhanh thành khẳng định đã sửa nguyên nhân.

## Cập nhật kế hoạch tiếp theo

Người dùng đã chốt kế hoạch xử lý BUG-008 trước rồi ENH-002. Đã tạo bốn phase
4–7 với 12 task, xem [kế hoạch thực thi](../ke-hoach/ke-hoach-bug-008-enh-002-2026-10-28.md).
Đây là cập nhật kế hoạch, chưa phải kết quả phục hồi hay triển khai tính năng.
