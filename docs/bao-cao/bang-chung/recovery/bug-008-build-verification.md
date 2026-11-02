# BUG-008 — kiểm chứng bản dựng phục hồi

Ngày kiểm tra: 28/10/2026. Checkout: `feature/offline-engine`, Python 3.12.15.
Không commit, push, tag, merge, ký số hoặc phát hành trong lượt này.

## Kết quả

- Khôi phục đủ 22/22 tệp theo ledger `bug-008-restored-files.json`; 18 tệp lấy
  từ HEAD đã đối chiếu, bốn tệp giữ branding/nội dung mới ở checkout IDE và hòa
  giải hợp đồng offline. Source đã tồn tại ngoài metadata task giữ nguyên hash.
- Builder từ chối đích đã tồn tại, đích nằm trong pack và thiếu notice/input bắt
  buộc trước khi tạo output. Ba hồi quy mới đạt.
- Full suite: 424/424 đạt trong 140,886 giây. `pip check`, hard-error Ruff,
  `git diff --check` và native GUI smoke đạt.
- Frontend production build và Chromium viewer: 16/16 đạt với sandbox/preload
  và cổng API loopback động.
- Fresh portable: 28.030 tệp, 22.654.743.222 byte. SHA-256 executable:
  `0c3c2d844ce2f61b6b917d851d8b159ed700b40581daf7e2a8757cca556c751f`.
- Manifest dữ liệu đầu vào và bản sao trong fresh build cùng SHA-256
  `2c5b6838509985b9f7f04bb9d6bf3bf872d41d2455de096ac86d3cf9c95d7535`.
  Builder chạy `pip check` và import portable bằng Python/runtime đi kèm.

## PDF thực bằng fresh portable

- PDF khoa học một trang: mức Nhanh dịch 12/19 đoạn; 7 đoạn được giữ nguồn do
  marker công thức, không cưỡng ép. Giữ 123/123 glyph toán, đúng trang/canvas,
  không rò marker hoặc ký tự thay thế, nguồn giữ nguyên. SHA-256 kết quả:
  `c52c4ef495a5eeb7237b42c28790c018d938e42386f0b6bed0bd084ea56219b8`.
- PDF scan một trang: OCR standard dịch 4/4 đoạn, không cảnh báo, đúng
  trang/canvas, nguồn giữ nguyên; model và font lấy từ chính pack portable.
  SHA-256 kết quả:
  `e6557a23690cdf96e01f28b19ce3dc91f6c8ccb5ffd01297240ef458f2176382`.
- Đã mở hai ảnh render ở 130/110 DPI: công thức, hai cột, chân trang và tiếng
  Việt scan rõ; không thấy chữ cắt, đè hoặc trang trắng.

Log: `tmp/phase4-unittest-final.log`, `tmp/phase4-viewer.log`,
`tmp/phase4-build.log`, `tmp/phase4-scientific.log`, `tmp/phase4-scan.log`.
Render/kết quả giữ ở `output/pdf/recovery-verify-scientific-20261028` và
`output/pdf/recovery-verify-scan-20261028`.

## Trạng thái gate

BUG-008 đạt `technical_verified`; Phase 5 được phép bắt đầu. Trạng thái PASS và
Git persistence vẫn pending vì phiên làm việc không được phép commit/push/tag.
Windows sạch, laptop RTX 3050 thật và phát hành không thuộc gate phục hồi này.

Artifact fresh build là bản tạm có marker P4-T3. Sau khi lưu bằng chứng, lệnh xóa
đệ quy chính xác đường dẫn đã bị cơ chế duyệt tự động từ chối; artifact được giữ
nguyên. Không có lệnh xóa khác được thử và bộ portable tốt không bị tác động.
