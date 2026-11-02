# Phase 6 — Gói nhẹ, tác vụ và giao diện (ENH-002)

## Goal
Bản offline có thể dùng pack nhẹ độc lập, kiểm tra khả năng xử lý theo máy và
giữ đúng lựa chọn của người dùng. Phụ thuộc Phase 5 technical_verified.

## Tasks
| Task | Kết quả | Phụ thuộc |
| --- | --- | --- |
| P6-T1 | Policy/token budget/cache đi xuyên job | Phase 5 |
| P6-T2 | Chuẩn bị/build lite/full hoàn toàn local | T1 + manifest |
| P6-T3 | Import local vào app-data, chọn lần mở sau | T2 |
| P6-T4 | API + UI recommendation/readiness/import/check | T1–T3 |

## Luồng người dùng
1. Ứng dụng xác minh gói đã chọn, đo snapshot nhẹ tại chỗ.
2. Thử mức đề xuất nền và hiển thị tiến trình; POST check trả 202 nhanh, GET capabilities
   chỉ đọc. Mức mới người dùng chọn được kiểm tra khi idle, không đổi job đang chạy.
3. Fresh full dùng balanced như hiện tại; fresh lite có thể mặc định fast theo pack.
   Việc nhận default chỉ diễn ra trước khi người dùng chỉnh; refresh không đổi lựa chọn.
4. Nhanh/Cân bằng/Chất lượng cao luôn có trong danh sách. Thiếu gói và thiếu bộ nhớ có
   thông báo khác nhau. Profile chưa qua probe không được báo ready hay nhận job.
5. Ngay trước job, recheck snapshot nhẹ, freeze policy. Nếu readiness không còn hợp
   lệ, báo kiểm tra lại; không đợi probe dài trong request create-job 30 giây.
6. Nhập gói từ thư mục/USB có manifest; hash toàn bộ trước publish catalog. Chọn gói
   mới áp dụng khi người dùng khởi động lại và queue idle. Giữ active pack cũ.

## An toàn
- Không tải trọng số/tokenizer/runtime từ Internet. Nếu thiếu, giữ nguồn/báo lý do.
- Input token budget gồm prompt, source, marker, chỗ cho output; không cắt đoạn,
  không coi ký tự là token, không mặc định endpoint tokenize chưa kiểm chứng có sẵn.
- Policy bất biến per-job; không dùng biến global có thể đổi khi probe/poll/import.
- OOM không đổi profile/AI mapping ngầm. CPU fallback cùng profile chỉ theo policy
  đã thử, không thay ngữ nghĩa tên mức.
- Import chỉ copy dependency manifest đã validate; chặn absolute path bên trong
  manifest, traversal, symlink/reparse; free-disk/quota/cancel và atomic registry.
- Không xóa gói/model có sẵn để import. Không tự sửa firewall/driver hoặc dừng AI riêng.
- Giữ token mỗi phiên, private port/CSP, context isolation/sandbox và guard PDF.
- Hướng dẫn, lỗi, API/log public không lộ model/vendor/private URL/path.

## Gate
Unit/API + Chromium cases mới và viewer cũ đều đạt. Lite chỉ có fast vẫn chạy;
full v1 không hồi quy. Quá budget/thiếu bộ nhớ/corrupt/cancel không hỏng PDF nguồn.
Cấu trúc resource cache namespace mới tách policy/gói, không dùng free-memory
tức thời như cache key. Các kết quả thực trên hardware nằm ở Phase 7.

## Ngân sách ổ đĩa
Chuẩn bị từ pack giữ lại, ghi trực tiếp closure vào đích portable mới nếu phù hợp;
không tạo thêm full staging 21 GB. Phase 6 dựng lite thử; full v2 thực dựng một
lần ở P7-T1. Luôn đo free-disk và peak bytes trước copy, chừa policy dự phòng ban
đầu 10 GB. Không xóa pack đã cài hoặc bộ baseline để giải quyết thiếu dung lượng.

