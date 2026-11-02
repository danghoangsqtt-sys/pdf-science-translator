# Đọc cấu hình máy Windows ngoại tuyến

`hardware_service` chỉ đọc thông tin tại máy để chọn policy/gói phù hợp. Không có
telemetry, request mạng, quyền quản trị, thay driver/firewall hoặc tự cài công cụ.

## Nguồn và đơn vị

- RAM tổng/khả dụng: Win32 `GlobalMemoryStatusEx`, byte.
- GPU: `nvidia-smi.exe` ở một trong hai đường dẫn hệ thống cố định; truy vấn tên,
  VRAM tổng/khả dụng và phiên bản driver bằng argv cố định, `shell=False`, timeout
  ba giây. Không truy vấn UUID, serial hoặc process list.
- CPU: tên processor local, kiến trúc và số logical processor.
- Disk: tổng/trống của ổ chứa ứng dụng, byte; path không xuất hiện trong public DTO.

Snapshot có TTL năm giây và có async wrapper chạy bằng thread để không chặn event
loop. `None` nghĩa là không đọc được; số 0 vẫn là giá trị đo được và không bị đổi
thành `unknown`. Không cộng RAM với VRAM.

Trên Windows WDDM, VRAM khả dụng có thể đổi nhanh và khác số ứng dụng thực tế có
thể cấp phát. Snapshot chỉ là đầu vào cho probe local, không phải chứng nhận máy.
Permission, driver thiếu, timeout hoặc định dạng lạ trả trạng thái `unknown` an
toàn. Nghiệm thu laptop RTX 3050 4 GB phải dùng số đo thật riêng ở Phase 7.

## Smoke trên máy phát triển — 28/10/2026

Service đọc được 34.088.599.552 byte RAM, GPU RTX 3060 với 12.884.901.888 byte
VRAM, 20 logical processor và 38.275.256.320 byte disk trống. Đây là máy phát
triển khác cấu hình đích; số liệu chỉ chứng minh đường đọc thật hoạt động.
