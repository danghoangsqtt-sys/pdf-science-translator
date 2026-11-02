# Windows ngoại tuyến — triển khai và kiểm chứng 28/10/2026

Bản Windows portable đã dựng và mở thành công từ tài nguyên đóng gói. Giao diện
chỉ có **Nhanh / Cân bằng / Chất lượng cao**, mặc định Cân bằng. Nguồn triển khai
ở worktree `feature/offline-engine`, `.claude/worktrees/frosty-ritchie-f4e306`;
không gộp hay ghi đè các thay đổi đang có ở checkout IDE.

## Bộ để mở thử

- Chạy `build/windows-offline-2026-10-28/PDFTranslate.exe` trong worktree này.
- Giữ nguyên toàn bộ thư mục khi sao chép; bộ hiện tại khoảng **22,66 GB**.
- Gói dữ liệu: **1.017 file, 21.232.118.945 byte**, chưa tính manifest.
- Python 3.12 và các module native nằm trong `resources/python_runtime`, đã kiểm
  tra `sys.prefix` và đường dẫn module không phụ thuộc Python cài ở máy phát triển.
- Worker lấy từ `resources/offline-data/worker`, dùng dữ liệu riêng; không kết nối
  service AI được người dùng cài độc lập. Đã mở giao diện để người dùng kiểm tra.

## Thay đổi thực thi

`pdf2zh/offline.py` chặn DNS/TCP/UDP ngoài loopback trong Python, kiểm tra hash và
đường dẫn tài nguyên trước khi khởi động, rồi kiểm tra thay đổi/thiếu file trước
tác vụ. Marker `offline-edition.json` giữ chính sách ngoại tuyến ngay cả khi mất
thư mục dữ liệu. Thiếu tài nguyên thì dừng có kiểm soát, không tự tải qua mạng.

Electron chỉ cho renderer tải tài nguyên cục bộ và cổng API riêng của phiên;
khóa cửa sổ/liên kết ngoài và menu mặc định. Worker chạy riêng với tính năng
cloud tắt. API dùng token từng phiên, chỉ nhận profile; từ chối engine/model,
trường không hỗ trợ và profile lạ. Không có endpoint công khai liệt kê model,
Swagger/CDN hay kiểm tra/cập nhật trực tuyến trong bản này.

UI, DTO trạng thái, cảnh báo và lỗi công khai dùng tên mức xử lý/mã trung tính.
Ánh xạ, raw exception và stdout/stderr worker không đi vào luồng người dùng.
Tài nguyên nội bộ và các giấy phép vẫn được giữ; không cam kết giấu trước người
có quyền đọc/phân tích toàn bộ máy hoặc bộ phân phối.

Nhanh dùng ngân sách ít hơn; Cân bằng có thử lại giới hạn; Chất lượng cao có thêm
lượt cứu và bộ xử lý dự phòng. Mọi mức giữ cùng guard marker, độ dài, glyph và fit.
Cache phân biệt profile, revision xử lý và digest manifest dữ liệu để không dùng
lại bản dịch của gói trọng số cũ dưới cùng một alias.

API tự bật OCR tiêu chuẩn an toàn cho trang ảnh. Hai bộ OCR dùng đường dẫn local
tường minh; font lớp chữ OCR và giấy phép đi cùng manifest. Bài scan thật đã bắt
được thiếu font mà kiểm tra nhận dạng riêng chưa phát hiện; đã sửa và có hồi quy.

## Kết quả kiểm tra

| Gate | Kết quả |
| --- | --- |
| Python 3.12, toàn bộ unittest | **421/421**, 11,730 giây ở lượt cuối |
| `pip check` | Không có dependency hỏng, cả venv và Python portable |
| Ruff `E9,F63,F7,F82` | Đạt |
| Frontend TypeScript/Vite + Chromium | **16/16 tương tác**, không lỗi renderer |
| Native GUI/layout/OCR smoke | Exit 0; tải runtime native thật |
| Python portable/module native | Đường dẫn nằm trong bộ portable |
| Đồng bộ nguồn → gói | 19 module Python khớp byte với nguồn cuối |
| UI bản đóng gói | Chọn PDF, dịch, tải kết quả, hai khung và cảnh báo hoạt động |
| Cổng/API | Preload sandbox thật, cổng khác 8089, token và Origin `null` được kiểm tra |
| Chính sách mạng | Kiểm thử DNS/TCP/UDP bị chặn; snapshot tiến trình sản phẩm chỉ có loopback |
| Git diff whitespace | Đạt; có thông báo chuẩn hóa CRLF/LF từ Git |

Chromium kiểm tra thêm trạng thái đang chuẩn bị không báo sẵn sàng giả; ba lựa
chọn, cuộn liên tục, đồng bộ hai chiều, Ctrl+wheel, kéo, bật/tắt đồng bộ, điều
hướng trang và tài liệu 200 trang chỉ render canvas gần vùng nhìn thấy.

Mẫu khoa học là trang thứ ba trích từ PDF 9 trang đã audit; nguồn gốc không bị sửa.
Nguồn trích SHA-256 `4b97680c5b720a38634bf87e308fb17ed698fdb3409ce36ee9abe1718d9c0063`.
Không dùng cache khi đo:

| Mức | Thời gian dịch | Đoạn dịch | Giữ nguồn | Glyph toán bị mất |
| --- | --- | --- | --- | --- |
| Nhanh | 27,00 giây | 12/19 | 7 vì marker | 0/123 |
| Cân bằng | 79,94 giây | 16/19 | 2 marker, 1 câu trả lời không đáng tin | 0/123 |
| Chất lượng cao | 160,49 giây | 19/19 | 0 đoạn cần dịch | 0/123 |

Ba bản có cùng số trang/canvas, không lộ marker hoặc ký tự thay thế. Đã render
và đọc cả ba ảnh; công thức, hai cột, heading và chân trang còn nguyên. Các phần
được quy tắc bảo vệ chủ động giữ lại không tính là đoạn dịch thất bại. Kết quả
không chứng minh mọi câu dịch đều đúng về nghĩa; thuật ngữ vẫn cần người đọc soát.
Khởi tạo worker gồm kiểm tra hash trên máy thử mất khoảng 29–45 giây ở các lượt đo.

OCR với Python portable, policy chặn mạng ngoài máy đang bật: tiêu chuẩn nhận
đúng câu mẫu trong 4,55 giây; nâng cao 12,36 giây. PDF chỉ có ảnh sau sửa font dịch
**4/4 đoạn**, không cảnh báo OCR, nguồn giữ nguyên, cùng canvas/số trang; 35,30 giây
gồm khởi tạo/kiểm tra dữ liệu. Đã xem ảnh render một trang đầu ra, chữ Việt rõ và
đúng vị trí tương ứng.

Bằng chứng sinh cục bộ, không đưa PDF/weights vào Git:

- `output/pdf/owned-profiles-2026-10-28/measurement.json`, các PDF/ảnh ba mức.
- `output/pdf/owned-profiles-2026-10-28/packaged-connections.json`.
- `output/pdf/packaged-scan-fixed-2026-10-28/measurement.json`, PDF và ảnh scan.
- `tmp/offline-release-tests.log`, `tmp/offline-viewer-handoff/result.json`.
- `tmp/packaged-ocr.log`, `tmp/offline-native-smoke.log`, `tmp/build-windows-offline.log`.
- Ảnh UI thật và bản xem trước: checkout IDE
  `.viepilot/ui-direction/windows-offline-2026-10-27/index.html`.
- Bộ kiến trúc 13 trang: checkout IDE
  `.viepilot/architect/windows-offline-2026-10-27/index.html`.

## Dựng lại hoàn toàn từ dữ liệu local

```powershell
# Trong webui/frontend, dependency đã có sẵn:
npm run build

# Trong root worktree; chọn thư mục đích mới, không ghi đè bộ đã có:
.\.venv312\Scripts\python.exe scripts\prepare_offline_pack.py `
  --output build\new-offline-data --worker C:\local-resources\worker.exe `
  --models D:\local-resources\models --ocr D:\local-resources\ocr
.\.venv312\Scripts\python.exe scripts\build_offline_windows.py `
  --output build\new-windows-portable --pack build\new-offline-data
```

`--worker` phải là executable runtime đã có kèm thư mục `lib` đầy đủ bên cạnh.
Công cụ dựng không tải dependency/trọng số, không chạm bộ AI người dùng và từ
chối thư mục đích đã tồn tại. Tài nguyên gốc được sao chép, không liên kết vào máy
phát triển. Giữ các notice/giấy phép đi kèm; đây chưa phải bước phát hành.

## Điều kiện còn lại

- Chưa có lượt nghiệm thu trên **Windows sạch, ngắt mạng vật lý/VM** và ma trận
  CPU/RAM/GPU khác nhau. Chưa chốt cấu hình tối thiểu hoặc tốc độ cho máy khác.
- Snapshot loopback và guard ứng dụng không phải firewall sandbox cấp hệ điều
  hành cho mọi native code. Không thay đổi firewall/VPN/cấu hình bảo mật máy.
- Độ đúng thuật ngữ ở tài liệu mới vẫn cần đối chiếu; mức cao không cam kết tuyệt đối.
- Chưa kiểm kê/phê duyệt toàn bộ điều kiện phân phối bên thứ ba cho phát hành rộng,
  chưa ký số, chưa installer/ZIP công khai; bộ portable dùng để kiểm tra nội bộ.
- Không commit/push/tag/merge. Gate persistence của vp-auto còn pending; chưa ghi
  PASS cho phase. Các sửa đổi cũ và nguồn PDF được giữ nguyên.
