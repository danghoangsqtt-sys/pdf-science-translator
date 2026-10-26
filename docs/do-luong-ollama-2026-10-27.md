# Đo lường bộ dịch ngoại tuyến TranslateGemma (27/10/2026)

## Điều kiện đo

- Tài liệu: `Inception Score - trich 3 trang.pdf` (3 trang, khổ Letter 612×792 pt,
  bài báo LaTeX dày công thức). Không đưa tệp PDF vào repo.
- Máy: Windows 11, GPU RTX 3060 12 GB, Ollama 0.40.4, dịch Anh → Việt.
- Lệnh: `scripts/translate_pdf.py --engine ollama --model <mô hình> --ignore-cache`,
  2 luồng (mặc định cho Ollama).
- Mỗi lần chạy bắt đầu **nguội**: mô hình được `ollama stop` trước, nên thời gian
  đã gồm cả lúc nạp mô hình vào GPU (khoảng 20 giây với 12b).
- Tệp gốc được so SHA-256 trước và sau: không thay đổi.

## Kết quả

| Chỉ số | 12b, chưa có thử lại | **12b (bản giao)** | **4b (bản giao)** |
| --- | --- | --- | --- |
| Thời gian toàn tài liệu | 145 giây | 260 giây | 81 giây |
| Giây/trang (trung bình) | 48,5 | 86,8 | 27,0 |
| Giây cho trang 1 / 2 / 3 | 55 / 47 / 42 | 66 / 105 / 89 | 20 / 35 / 25 |
| Đoạn đã dịch | 27/43 (63%) | 34/43 (79%) | 38/43 (88%) |
| Đoạn giữ gốc: mất ký hiệu | 16 | 7 | 5 |
| Đoạn giữ gốc: bộ dịch bịa thêm nội dung | – | 1 | 0 |
| Đoạn giữ gốc: không vừa vùng | 0 | 1 | 0 |
| Công thức nội dòng nằm trong đoạn giữ gốc | 76/97 | 56/97 | 9/97 |
| Công thức đánh số (1)–(6) hiển thị đúng | 6/6 | 6/6 | 6/6 |
| Ký hiệu toán (CMMI/CMSY/CMEX/CMBX) bị mất | 0 | 0 | 0 |
| Số trang so với gốc | 3 = 3 | 3 = 3 | 3 = 3 |
| Khổ giấy so với gốc | giống hệt | giống hệt | giống hệt |
| Ký hiệu nội bộ lộ ra (`{vN}`, `<bN>`, `<sN>`) | 0 | 0 | 0 |

"Công thức nội dòng" là các chỗ lõi thay bằng `{vN}` trong đoạn văn. Công thức
trong đoạn đã dịch được vẽ lại bằng nét gốc ở vị trí mới; công thức trong đoạn
giữ gốc vẫn là tiếng Anh nguyên vẹn. Dấu ngoặc, chữ số và chữ đứng như `exp`,
`ln` của phông CMR nằm trong câu văn nên được vẽ lại bằng phông chữ thường (95
ký tự, như nhau ở mọi bộ dịch); trên ảnh trang chúng vẫn hiển thị đầy đủ.

## Đánh giá bằng mắt (ảnh từng trang so với bản gốc)

- **12b** dịch đúng thuật ngữ hơn: giữ tên "Inception Score", dùng "phân bố biên"
  cho *marginal distribution*. Nhưng tiếng Việt dài hơn nên vài đoạn cột phải trang
  2–3 và đề mục 3 bị thu nhỏ chữ rõ rệt.
- **4b** nhanh gấp ba và giữ ký hiệu tốt hơn, nhưng **sai nghĩa thuật ngữ**:
  "Inception Score" thành "chỉ số khởi đầu"/"Điểm Khởi đầu" ở ba đề mục,
  "marginal class distribution" thành "phân bố của các nhóm nhỏ". Không nên dùng
  4b cho tài liệu chuyên ngành mà không có người đọc lại.
- Cả hai: phân số $p(y=1|x)=\frac{\dots}{\dots}$ trong đoạn Bayes nằm sát dòng
  dưới; câu cuối trang 1 vắt sang trang 2 nên bị dịch như câu trọn vẹn và thu nhỏ;
  đoạn giữ gốc được dàn lại dòng nên còn dấu gạch nối của bản gốc ("In- ception").

## Những gì đã sửa nhờ lần đo này

| Hiện tượng với translategemma | Cách xử lý |
| --- | --- |
| Đoạn dày công thức làm rơi `<bN></bN>` | Dịch lại riêng đoạn hỏng với công thức viết dạng `{N}`, rồi lấy mẫu 2 lần (seed cố định); cứu 7–9/16 đoạn. Mọi bản vẫn qua bước kiểm tra ký hiệu. |
| Trả `<b0>` thiếu nửa đóng | Thêm `</b0>` chỉ khi số đó không xuất hiện ở nơi khác |
| Thêm dấu chấm cuối đề mục | Bỏ dấu chấm khi bản gốc không có |
| Bọc công thức trong backtick | Bỏ backtick khi bản gốc không có |
| Bịa thêm nội dung (1,94× độ dài) | Bản dịch dài quá 1,6× + 20 ký tự bị thử lại rồi từ chối; 79 bản dịch hợp lệ nằm trong khoảng 0,77–1,53× |
| Đề mục LaTeX mất chữ đậm (`NimbusRomNo9L-Medi`) | Kiểu chữ = descriptor ∪ tên phông (lỗi có sẵn, mọi bộ dịch) |

## Tệp kết quả

Trong thư mục `ket-qua-thu-nghiem` của người dùng (không nằm trong repo):

- `Inception Score - trich 3 trang-vi-translategemma-12b.pdf`
- `Inception Score - trich 3 trang-vi-translategemma-4b.pdf`
- `Inception Score - trich 3 trang-vi-translategemma-12b-lan1-chua-thu-lai.pdf`
  (bản trước khi có cơ chế thử lại, để so sánh)
