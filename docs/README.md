# Tài liệu

| Thư mục | Nội dung |
| --- | --- |
| [`huong-dan/`](huong-dan/) | Cài đặt, chạy từ mã nguồn, phát hành Android |
| [`kien-truc/`](kien-truc/) | Bản đồ mã nguồn, nhận diện phần cứng |
| [`bao-cao/`](bao-cao/) | Audit, đo lường, kiểm thử; mỗi file ghi ngày trong tên |
| [`bao-cao/bang-chung/`](bao-cao/bang-chung/) | Manifest, hash và biên nhận của các lần dọn/phục hồi; giữ nguyên, không sửa |
| [`ke-hoach/`](ke-hoach/) | Kế hoạch triển khai và xử lý lỗi |
| [`brainstorm/`](brainstorm/) | Phiên brainstorm của ViePilot (giữ đúng đường dẫn này) |
| [`tham-khao/`](tham-khao/) | Prompt, ghi chú nghiên cứu giao diện |

Bắt đầu từ [`huong-dan/installation-guide.md`](huong-dan/installation-guide.md).
Quy tắc bảo toàn bố cục là hợp đồng sản phẩm, nằm ở
[`../references/preservation-rules.md`](../references/preservation-rules.md).

## Ngoài git

Toàn bộ dự án nằm trong một thư mục. Những thứ không phải mã nguồn nằm trong
hai thư mục ở gốc, được git bỏ qua:

`_workspace/`:

| Thư mục | Nội dung |
| --- | --- |
| `samples/` | PDF mẫu để dịch thử (trước đây `test_samples/`) |
| `output/` | Kết quả dịch thử, ảnh demo |
| `scratch/` | Log, script và môi trường tạm của các lần audit (trước đây `tmp/`) |
| `backup-*/` | Bản vá và bản sao lưu trước các thay đổi lớn |

`BAN-CAI-DAT/`: hai bản cài portable (máy cấu hình mạnh, máy cấu hình yếu)
kèm hướng dẫn cài đặt, để chép sang máy khác. Gói dữ liệu trung gian dùng khi
build là bản sao của kho model, nên xóa sau mỗi lần build.
