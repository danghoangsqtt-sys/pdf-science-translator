# Hướng dẫn thực thi Windows Offline

- Dùng `.venv312/Scripts/python.exe` và bundled PDF core.
- Nguồn và kết quả có sẵn bất biến. Không sửa các phần branding/viewer dang dở
  ngoài những điểm tích hợp cần thiết; không merge giữa hai checkout.
- Chỉ loopback cho runtime. Bản offline không có đường cloud/download/update.
- Không trả model/vendor/path/lệnh tải hoặc raw exception qua API/UI/log công khai.
- Không hạ guard marker/glyph/fit để tăng tốc. Thiếu dữ liệu thì fail closed.
- Mọi tài nguyên/gói chạy thử trong `build/`, `tmp/`, `output/`, không track weights.
- Gate: unittest, pip check, hard Ruff, frontend build + viewer, smoke, PDF render.
- Chưa được cấp phạm vi commit/push/tag/merge; ghi persistence pending sau xác minh.
