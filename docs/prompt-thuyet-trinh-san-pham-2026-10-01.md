# Prompt tạo bài thuyết trình PDF Translate

## Tư liệu dùng trong bài

- Ảnh chụp cửa sổ ứng dụng desktop thật: [`app-screenshot-final.png`](../output/presentation-demo-2026-10-01/app-screenshot-final.png).
- Trang PDF tiếng Anh dùng để thử: [`demo-source-page.png`](../output/presentation-demo-2026-10-01/demo-source-page.png), [PDF gốc](../output/presentation-demo-2026-10-01/math-physics-final-demo.pdf).
- Trang PDF tiếng Việt sau khi chạy sản phẩm: [`demo-translated-page.png`](../output/presentation-demo-2026-10-01/demo-translated-page.png), [PDF kết quả](../output/presentation-demo-2026-10-01/math-physics-final-demo-vi.pdf).

Các tệp ảnh và PDF trên là hiện vật thử nghiệm cục bộ trong `output/`; thư mục này được Git bỏ qua. Khi chuyển prompt cho công cụ tạo slide, đính kèm ba ảnh PNG và, nếu công cụ hỗ trợ, hai PDF.

## Prompt sao chép và sử dụng

```text
Hãy tạo bài trình chiếu 16:9 bằng tiếng Việt để tôi báo cáo sản phẩm PDF Translate trong 7–9 phút. Đối tượng nghe là giảng viên, sinh viên và người dùng tài liệu chuyên môn. Giọng điệu rõ ràng, đáng tin, tập trung vào tình huống sử dụng và lợi ích thực tế. Không trình bày kiến trúc, thư viện, mô hình AI, ngôn ngữ lập trình hoặc quy trình phát triển, trừ khi có một câu giải thích ngắn thực sự cần cho người dùng.

Chỉ dùng ba ảnh tôi đính kèm làm hình giao diện và bằng chứng demo:
1. app-screenshot-final.png — ảnh chụp thật giao diện desktop, với một PDF đang ở hàng đợi.
2. demo-source-page.png — bản render của PDF tiếng Anh về toán học và vật lý.
3. demo-translated-page.png — bản render của PDF tiếng Việt do sản phẩm tạo ra.
Không vẽ lại giao diện, không tạo ảnh giả được gắn nhãn là ảnh chụp sản phẩm. Đặt chú thích rõ đâu là ảnh chụp ứng dụng, đâu là trang PDF trước/sau.

Thông tin đã kiểm chứng:
- PDF Translate là ứng dụng dịch PDF, ưu tiên giữ bố cục trang, công thức, bảng và hình. Giao diện desktop cho phép chọn/kéo thả tệp hoặc thư mục, chọn ngôn ngữ đích, chọn chế độ OCR cho trang scan, theo dõi hàng đợi và mở kết quả. Mặc định là tiếng Việt. Bản desktop có phiên bản hiển thị 0.3.0 trong ảnh.
- Ca thử sử dụng một tài liệu tiếng Anh tự tạo, một trang A4, gồm đạo hàm, định luật II Newton và động năng. Bản tiếng Việt được tạo bằng chế độ handoff của chính dự án sau khi chế độ Google mặc định bị HTTP 429 trong môi trường thử.
- Kiểm tra đầu ra: 1/1 trang; khổ trang 595 × 842 pt ở cả hai bản; 10/10 đoạn cần dịch đã được cung cấp bản dịch; cả bốn dòng công thức x(t), v(t), F = m*a và E_k còn nguyên; không có marker nội bộ trong văn bản trích xuất; không có hộp chữ vượt ra ngoài trang. Đây là kết quả của một ca thử, không phải tỷ lệ thành công trên mọi tài liệu.
- Một số vùng khó như bảng không nhận diện chắc chắn, hình, tài liệu tham khảo hoặc PDF scan phức tạp có thể được giữ nguyên. OCR đang ở mức thử nghiệm; người dùng cần rà lại thuật ngữ, công thức và bố cục khi dùng tài liệu quan trọng.

Thiết kế 8 slide, tối đa 35 từ chính trên mỗi slide (không tính chú thích ảnh), mỗi slide có một thông điệp chính. Dùng bảng màu xanh lá đậm/trắng gần với ảnh ứng dụng, chữ lớn, nhiều khoảng trắng. Có ghi chú thuyết trình 2–4 câu cho từng slide. Bố cục đề xuất:

1. Trang bìa: “PDF Translate — Đọc tài liệu chuyên môn bằng tiếng Việt, giữ cách trình bày quen thuộc”. Dùng logo nhỏ cắt từ ảnh ứng dụng nếu cần; không thêm biểu tượng tự bịa.
2. Vấn đề người dùng: tài liệu toán, vật lý ở dạng PDF khó đọc nhanh khi phải tự dịch, nhất là khi công thức và bố cục bị xáo trộn. Dùng một tình huống học tập/nghiên cứu cụ thể, tránh số liệu thị trường không có nguồn.
3. Cách sử dụng trong ba bước: thêm PDF → chọn tiếng Việt/chế độ phù hợp → nhận PDF dịch và rà lại. Trình bày thành luồng đơn giản cho người dùng cuối.
4. Giao diện sản phẩm: đặt app-screenshot-final.png lớn, dùng 3 nhãn gọn chỉ vùng chọn tệp, ngôn ngữ/OCR và hàng đợi. Chú thích “Ảnh chụp ứng dụng desktop, tài liệu mẫu đang chờ dịch”. Không gọi ảnh này là trạng thái dịch hoàn tất.
5. Minh họa trước/sau: đặt demo-source-page.png và demo-translated-page.png cạnh nhau, cùng tỷ lệ. Khoanh nhẹ phần văn xuôi đã chuyển sang tiếng Việt và các dòng công thức được giữ. Chú thích “Ca thử 1 trang A4 về toán và vật lý; bản dịch tạo bằng chế độ handoff”.
6. Giá trị ứng dụng: ba nhóm người dùng — sinh viên đọc giáo trình, giảng viên chuẩn bị tài liệu, kỹ sư/người nghiên cứu đọc tài liệu chuyên ngành. Mỗi nhóm một lợi ích cụ thể, không hứa độ chính xác tuyệt đối.
7. Kết quả kiểm tra và giới hạn: hiển thị các số 1/1 trang, 10/10 đoạn handoff, 4/4 dòng công thức, cùng khổ trang; bên cạnh là ghi chú ngắn “cần kiểm tra lại nội dung quan trọng; OCR scan phức tạp có thể chỉ dịch một phần”. Nêu lỗi HTTP 429 của dịch Google mặc định như giới hạn của buổi thử, không che giấu và không suy diễn đó là lỗi của mọi lần dùng.
8. Kết luận và lời mời dùng thử: “Chọn một PDF chuyên môn của bạn, xem bản dịch cạnh bản gốc, rà lại rồi sử dụng.” Kết bằng lợi ích tiết kiệm công thao tác và giữ tài liệu dễ đối chiếu; không đưa ra con số tiết kiệm thời gian chưa đo.

Xuất bản trình chiếu có thể chỉnh sửa và ghi chú thuyết trình. Kiểm tra ảnh không bị cắt, chữ Việt có dấu hiển thị đúng, và slide 5 đủ lớn để thấy công thức. Nếu không truy cập được ảnh đính kèm, để khung giữ chỗ với đúng tên tệp và yêu cầu tôi bổ sung; không tự tạo ảnh thay thế.
```
