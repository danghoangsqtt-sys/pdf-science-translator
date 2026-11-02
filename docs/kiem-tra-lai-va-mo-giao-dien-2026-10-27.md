# Kiểm tra lại và mở giao diện — 27/10/2026

## Kết luận

Đã mở cửa sổ Electron thật của worktree `feature/offline-engine`. Trạng thái
quan sát được: **Backend sẵn sàng**, **Ollama sẵn sàng**, model mặc định
`translategemma:12b`. Backend thực tế chạy `.venv312/Scripts/python.exe`,
lắng nghe `127.0.0.1:8089`. Để cửa sổ ở phía trước cho người dùng chọn PDF;
không tự gửi tài liệu dịch hoặc ghi đè kết quả.

## Audit theo tầng

| Tầng | Kết quả |
| --- | --- |
| Tier 1 — Trạng thái | Nhật ký audit khớp request. Các BUG-001 đến BUG-005 đã đóng; bổ sung BUG-006 đã sửa, BUG-007 và ENH-001 đang mở. Chưa có hệ thống phase/ROADMAP/HANDOFF; không suy diễn phase hoàn tất. |
| Tier 2 — Tài liệu | Giữ các báo cáo cũ làm lịch sử; bổ sung kết quả kiểm tra lại và hướng dẫn runtime thực tế. Thay đổi vẫn ở worktree, chưa merge vào checkout IDE. |
| Tier 3 — Runtime/chất lượng | Gate chức năng đạt, có 2 vấn đề còn mở dưới đây; sửa chênh lệch runtime khởi động Electron. |

## Vấn đề còn lại

| Mức độ | Vấn đề | Bằng chứng / việc cần làm |
| --- | --- | --- |
| Medium — BUG-007 | Khởi tạo native layout/OCR chậm bất thường | Suite chuẩn: 403/403 đạt trong 131,879 giây. Lượt đo có chặn HTTP: 403/403 đạt trong 114,902 giây; riêng bài native smoke 109,662 giây, bài kế tiếp 1,532 giây. Cần profile từng bước native; chưa xác định chính xác nguyên nhân. |
| Medium — ENH-001 | Thuật ngữ model chính chưa ổn định | Bản PDF ở audit trước còn “mô hình sinh học” cho “generative models” và tên metric không thống nhất. Cần kiểm chứng glossary/domain trên cả model chính; chưa coi bản dịch là đã duyệt chuyên môn. |

Một heading trong mẫu trước được giữ gốc theo quy tắc fit; đây là fallback
bảo toàn được báo rõ, không coi là công thức bị hỏng. Những giới hạn của
macOS/Android/bộ cài và engine cloud chưa kiểm chứng vẫn được nêu ở báo cáo trước.

## Đã sửa trong bước mở ứng dụng

**BUG-006:** Electron phát triển chọn `.venv` Python 3.11 cũ trước đây. Đã ưu
tiên `.venv312`, build lại và xác nhận trực tiếp đường dẫn Python trong log
khởi động. Không thay runtime bản đóng gói hoặc venv cũ của người dùng.

## Kiểm chứng hiện tại

- `unittest discover`: **403/403 đạt**, không skip; đã tái hiện sự chậm thay
  vì suy luận từ số bài đạt.
- `pip check`, hard-error Ruff: đạt.
- Viewer: hồi quy gutter + **13 ca Chromium đạt**, không lỗi renderer.
- Build TypeScript/Vite sau thay đổi launcher: đạt.
- Cửa sổ Electron thật: logo tải được, bố cục hiển thị, backend/model đều sẵn
  sàng; log API health/engines trả 200. Không phát hiện lỗi CORS chặn cửa sổ
  file URL trong lần mở thực tế này.

Không lặp lại ca dịch GPU 13 phút vì không đổi engine PDF. Bằng chứng PDF của
phiên trước được giữ nguyên. Không commit, push hoặc merge.

## Guardrails tiếp tục

Giữ contract của `.viepilot/audit-report.md`; bổ sung yêu cầu đo riêng các
bước native và xác nhận runtime mà Electron thực sự chọn. Không dùng mock
thay smoke native thật, và không dùng tỷ lệ đoạn để khẳng định thuật ngữ đúng.

Request tiếp theo: `BUG-007`, `ENH-001`; có thể lập kế hoạch bằng
`vp-evolve BUG-007 ENH-001` khi xử lý hai vấn đề này.
