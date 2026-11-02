# Đánh giá laptop và đề xuất kiểm tra cấu hình — 28/10/2026

Cấu hình người dùng cung cấp: Core i7 thế hệ 12, RAM 24 GB, RTX 3050 laptop
VRAM 4 GB. **Nên bổ sung phân tích cấu hình và chọn gói cục bộ phù hợp.** Chưa đo
trên chính laptop nên đây là khuyến nghị kỹ thuật, chưa phải chứng nhận tương thích.

## Đánh giá khả năng chạy

| Thành phần | Nhận định |
| --- | --- |
| GPU 3050 | Thuộc nhóm GPU được runtime hỗ trợ; vẫn phải kiểm tra driver và phiên bản runtime đóng gói. |
| VRAM 4 GB | Giới hạn chính. Windows/màn hình, trọng số, KV cache và bộ đệm cùng dùng bộ nhớ; không so sánh đơn thuần kích thước tệp model với 4 GB. |
| RAM 24 GB | Có khả năng hỗ trợ gói nhẹ và chạy kết hợp CPU/RAM; RAM trống thực tế và ứng dụng khác quyết định dư địa. RAM không cộng trực tiếp thành VRAM. |
| i7 thế hệ 12 | Có thể hỗ trợ phần xử lý trên CPU, nhưng chưa biết mã CPU, giới hạn điện/nhiệt hoặc tốc độ trên máy thực. |
| SSD | Cần kiểm tra dung lượng trống, thời gian sao chép và vùng tạm. Bộ đầy đủ hiện khoảng 22,66 GB. |

Trọng số gói nhẹ hiện khoảng 3,3 GB theo danh mục phát hành; không có nghĩa nó sẽ
nằm trọn trong GPU 4 GB khi chạy. Có thể cần kết hợp GPU với RAM/CPU. Gói lớn
khoảng 8,1 GB không thể nằm trọn trong 4 GB VRAM; có thể chạy một phần trên CPU
nếu đủ RAM nhưng không mặc định hứa tốc độ tốt. Dùng **Nhanh** làm lựa chọn thử
đầu tiên; đo một trang có công thức và một trang scan trên laptop trước khi cho
phép các mức còn lại. Không suy ra tốc độ laptop từ máy desktop đã audit.

Nguồn chính thức: [GPU được hỗ trợ](https://docs.ollama.com/gpu),
[cách phân bố CPU/GPU và bộ nhớ](https://docs.ollama.com/faq),
[context và bộ nhớ](https://docs.ollama.com/context-length),
[trọng số gói nhẹ](https://ollama.com/library/translategemma:4b),
[trọng số gói lớn](https://ollama.com/library/translategemma:12b).

## Khoảng cách trong mã hiện tại

- `pdf2zh/translator.py:733` đặt `num_ctx=8192` cho mọi máy. Chưa có ngân sách
  context, RAM/VRAM hoặc kiểm tra khả năng nạp theo thiết bị.
- `pdf2zh/offline.py` yêu cầu đầy đủ ba alias và bộ dự phòng; `runtime_service.py`
  cũng kiểm tra toàn bộ chúng trước khi báo ready. `capabilities()` hiện báo
  sẵn sàng theo toàn bộ runtime, chưa theo tài nguyên cần cho từng mức.
- `scripts/prepare_offline_pack.py` luôn đóng toàn bộ bộ dữ liệu. Chưa có pack
  nhẹ được xác thực độc lập. Xóa các model lớn khỏi bộ hiện tại sẽ làm sai hash/
  completeness và có thể khóa cả mức Nhanh; không dùng cách đó để giảm dung lượng.
- `OLLAMA_NUM_PARALLEL=1` và `OLLAMA_MAX_LOADED_MODELS=1` đã là nền tảng phù hợp
  để giới hạn tải đồng thời; vẫn cần kiểm chứng nạp/giải phóng và trường hợp thiếu bộ nhớ.

## Phạm vi nâng cấp đề xuất

1. Đo RAM tổng/trống, CPU/kiến trúc, GPU/VRAM tổng và **VRAM đang trống**, driver,
   dung lượng ổ chứa gói và thư mục tạm. Với NVIDIA ưu tiên số liệu runtime/NVML/
   `nvidia-smi`, không chỉ dựa vào trường `Win32_VideoController.AdapterRAM`.
2. Chạy phép thử ngắn cục bộ, có timeout và ngân sách bộ nhớ. Không quét tài liệu
   người dùng, không gửi thông số máy hoặc telemetry ra mạng.
3. Gán chính sách tài nguyên nội bộ: một tác vụ/lượt suy luận, chừa bộ nhớ cho
   Windows, giới hạn context/batch và dùng CPU cho OCR khi cần bảo vệ VRAM.
   Các mốc 2K/4K context chỉ là ứng viên thử nghiệm; phải tính cả prompt, marker,
   văn bản nguồn và chỗ cho đầu ra. Không cắt cụt đoạn để ép vừa bộ nhớ.
4. Thiết kế manifest có tài nguyên chung và yêu cầu theo từng profile. Cho phép
   một pack nhẹ hợp lệ chạy độc lập, có checksum/giấy phép/font/OCR đầy đủ.
   Không đổi ngầm ánh xạ chất lượng và không quảng bá mức chưa được kiểm chứng.
5. Giữ UI **Nhanh / Cân bằng / Chất lượng cao**. Hiện “Khuyên dùng Nhanh trên máy
   này”, “Có thể chậm hơn”, hoặc “Chưa đủ tài nguyên” thay cho tên AI. Mức chưa đủ
   điều kiện vẫn có lý do trung tính; không tự hạ mức đã chọn khi tác vụ đang chạy.
6. Nguồn gói mặc định là **bộ ngoại tuyến đã chuẩn bị hoặc nhập từ USB**. Máy
   laptop chọn gói có sẵn, không tự kéo model từ Internet. Nếu cần tải gói từ máy
   có mạng, công cụ chuẩn bị/phân phối riêng phải được chốt phạm vi; ứng dụng dịch
   vẫn ngoại tuyến từ lần mở đầu. Chưa thay đổi chính sách 100% offline hiện có.

## Nghiệm thu trước khi áp dụng

- Đo nguội/lặp trên laptop thật; không chỉ giả lập GPU 4 GB trên desktop.
- Gói thiếu/hỏng, driver không tương thích, ít RAM/VRAM, CPU-only, ổ gần đầy và
  timeout phải có lỗi trung tính, giữ PDF nguồn và không chuyển cloud.
- Dịch PDF văn bản, scan an toàn và công thức; kiểm tra glyph, marker, fit và render.
- Báo đúng tỷ lệ đoạn còn giữ nguồn. Model nhỏ hoặc context thấp không được giảm
  các chốt bảo toàn chỉ để tăng phần trăm dịch.
- Cache phải phân biệt gói, profile và chính sách tài nguyên mới.
- Hướng dẫn public/API/log không lộ tên model; không làm thay đổi firewall/VPN máy.

Đây là đề xuất audit, chưa triển khai tính năng phát hiện máy hoặc đóng gói nhẹ.
Yêu cầu theo dõi: `.viepilot/requests/ENH-002.md` trong checkout ngoại tuyến.
