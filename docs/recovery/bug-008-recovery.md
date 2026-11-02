# BUG-008 — phục hồi nguồn

Đã xác nhận 22 tệp thiếu trước phục hồi; 18 bản IDE trùng HEAD ngoại tuyến, 4 bản khác biệt được giữ nguyên trong snapshot để hòa giải.

Snapshot: `D:\DataAdmin\vp-pdf\.claude\worktrees\frosty-ritchie-f4e306\tmp\bug-008-source-snapshot-20261028.zip`. Model gốc và bộ portable tốt chỉ đọc, không sao chép hoặc thay đổi. Hai checkout không reset/merge/stage. Các tệp nguồn đang tồn tại có hash bảo vệ trong JSON cạnh báo cáo.

## Phục hồi P4-T2

22/22 đường dẫn đã phục hồi, ledger hash/lý do tại `bug-008-restored-files.json`. 18 tệp lấy HEAD đã đối chiếu; logo/CITATION/README/SKILL giữ branding IDE. README/SKILL thêm hợp đồng offline hiện hành, nội dung legacy được ghi rõ phạm vi. Giữ nguyên LICENSE/THIRD_PARTY_NOTICES. .gitignore bổ sung venv312/build frontend/models; không stage. Các nguồn bảo vệ ngoài metadata task giữ nguyên hash.
