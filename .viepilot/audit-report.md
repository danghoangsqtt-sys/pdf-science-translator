# Audit và hoàn thiện hệ thống — 27/10/2026

> Cập nhật lần kiểm tra sau: [báo cáo mở giao diện](../docs/bao-cao/kiem-tra-lai-va-mo-giao-dien-2026-10-27.md).
> Đã tái hiện native smoke chậm; hiện còn BUG-007 và ENH-001 mở. Kết quả và
> trạng thái đóng 5 request dưới đây là lịch sử của lần audit trước.

## Phạm vi

- Codebase sản phẩm PDF Translate; nhánh `feature/offline-engine`, worktree
  `D:/DataAdmin/vp-pdf/.claude/worktrees/frosty-ritchie-f4e306`.
- Checkout IDE `D:/DataAdmin/vp-pdf` đang ở `feat/domain-glossary`; phần Ollama
  trong ảnh phiên trước nằm ở worktree trên. Không chuyển nhánh hoặc chép đè
  thay đổi đang có ở checkout IDE.
- Đọc pipeline Python, quy tắc bảo toàn, translator/cache, CLI, job/API,
  desktop smoke và khung đọc PDF React/Electron. Bản đồ chi tiết:
  [codebase-architecture.md](../docs/kien-truc/codebase-architecture.md).
- Giữ bản sửa tham khảo/fallback/cache và giao diện đang dang dở. Không commit,
  push, merge, tag, đóng gói hay phát hành trong phiên audit.

## Tier 1 — Trạng thái dự án

Repo ban đầu chưa có `.viepilot/`, ROADMAP, HANDOFF hay phase state; không có
căn cứ để kết luận phase hoàn tất hoặc tự tạo tag. Các brainstorm có ở
checkout IDE (`docs/brainstorm/`), không coi những file chưa track đó là bị mất
chỉ vì không có ở worktree.

Lần này tạo nhật ký audit tối thiểu và 5 request, không khởi tạo roadmap giả.
BUG-001 đến BUG-005 đã xử lý và đóng sau kiểm chứng; không còn request đang mở
trong phạm vi tiếp nối phiên này. Các giới hạn chất lượng dịch nêu cuối báo cáo
vẫn còn, không được coi là đã giải quyết nhờ tỷ lệ dịch hoặc kiểm thử cấu trúc.
Không gán phiên bản frontend `1.0.0` hoặc core thượng nguồn `1.9.11` thành
phiên bản ứng dụng desktop `0.3.0`.

## Tier 2 — Tài liệu

| Phát hiện | Mức độ | Xử lý |
| --- | --- | --- |
| README còn số 278 test và các số dòng cũ | Low | Bỏ số đếm dễ lỗi thời; kết quả hiện tại nằm trong báo cáo đo. |
| Fallback/cache mới chưa có hướng dẫn | Low | Bổ sung cài/tắt/đổi fallback, phiên bản cache và việc từ chối đầu ra thiếu. |
| Skill cho phép 3.11, AGENTS yêu cầu 3.12 | Low | Chuẩn hóa hướng dẫn sang 3.12; tạo `.venv312` riêng, giữ nguyên venv 3.11 cũ. |
| Nhầm miễn phí Azure F0 theo giờ với theo tháng | Low | Tách hạn mức miễn phí theo tháng và tốc độ theo giờ; dẫn nguồn Microsoft. |
| Thiếu bản đồ các ranh giới Python/API/UI/Android | Low | Thêm tài liệu kiến trúc, cập nhật shared knowledge và lệnh QA viewer. |

Các ghi chép lịch sử được giữ nguyên. Không tìm thấy placeholder URL
`your-org`, `YOUR_USERNAME`, `YOUR_ORG`, `your-username` trong tài liệu được track.
Repo không có changelog/ma trận diagram theo phase; không suy diễn drift từ
những tài liệu chưa được thiết lập.

## Tier 3 — Mã nguồn, runtime và kiểm chứng

| ID | Phát hiện | Mức độ | Kết quả |
| --- | --- | --- | --- |
| BUG-001 | Ollama nhận JSON sai kiểu hoặc prefix bị cắt nhưng marker còn nguyên | High | Từ chối trước cache/render; cache revision 3; kiểm tra cache cũ vẫn còn nguyên nhưng không được dùng lại. |
| BUG-002 | Phiên trước chưa đo lại tham khảo/fallback/cache trên PDF 9 trang | High | Bảo toàn trang tham khảo không tiêu đề; giữ từng citation trên trang lẫn văn xuôi; fallback chỉ dùng khi có sẵn, cùng guard; không fallback về chính model dưới tên `:latest`. |
| BUG-003 | Kéo 100 px nhưng chỉ đi 92 px khi qua gutter | Medium | Giữ offset trong khoảng giữa trang; hồi quy hình học 8 px và tương tác Chromium thật. |
| BUG-005 | Logo hỏng dưới `file://` vì dùng đường dẫn `/icon.png` | Low | Đổi `./icon.png`; kiểm tra ảnh đã tải bằng `naturalWidth > 0`. |

### Kiểm thử

| Gate | Kết quả |
| --- | --- |
| Baseline trước bổ sung, chặn HTTP thật | 398/398 đạt, 10,604 giây, Python 3.11 cũ. |
| Sau bổ sung, chặn HTTP thật | **403/403 đạt, 12,183 giây, Python 3.12.15**; không skip. |
| Nhóm Ollama | 49/49 đạt; status/reply/backoff đều giả lập; HTTP thật bị chặn trong module. |
| `pip check` trên `.venv312` | Đạt. |
| Ruff `E9,F63,F7,F82` trên Python core/app/scripts/tests/backend | Đạt. |
| `app/gui.py --smoke-test` trên `.venv312` | Exit 0; nạp layout và cả hai profile OCR thật. |
| `git diff --check` | Đạt. |
| `npm run test:viewer` | 1 hồi quy gutter + **13 ca Chromium đạt**, build TypeScript/Vite đạt, không lỗi/cảnh báo renderer. |

Chưa tái hiện lần chạy 112 giây trong ảnh. Bài chậm nhất hiện tại là nạp
native layout/OCR (7,34 giây), tiếp theo là thử rollback updater (1,574 giây).
Không kết luận nguyên nhân của lần chậm cũ khi không có trace. Chốt HTTP phát
hiện venv 3.12 mới thiếu hai model OCR enhanced; đã bổ sung từ bản cục bộ cùng
phiên bản và kiểm tra SHA-256, không tắt smoke test để lấy kết quả đạt.

### PDF 9 trang

Nguồn là bản sao phiên trước `scratchpad/full9-src.pdf` (4.603.953 byte), không
ghi đè tài liệu của người dùng. SHA-256 nguồn:
`97f0a816cd21785f349145ef5f5ce87804aa167da4fdc862b5b6200bdd2e4dd4`.

Lần chẩn đoán trên venv 3.11 cũ, bỏ cache: **834,02 giây**, 98/99 đoạn có thể
dịch được dịch, fallback cứu 12 đoạn; 1 đoạn giữ gốc do fit dưới 50% cỡ chữ.
Tất cả 9 trang giữ canvas; không lộ marker, không span vượt trang, không mất
glyph toán trong phép đối chiếu font/glyph ID. Trang tham khảo số 7 giống
nguồn từng pixel khi render 140 DPI. Đã xem toàn bộ contact sheet và trang
công thức, bảng, hình, tham khảo ở độ phân giải đọc được.

Có một NUL trong text extraction trang 2, **đã có trong nguồn**: font CMEX10,
bbox `(378.3160, 658.3423, 382.8789, 668.3049)`, giữ đúng font/bbox ở đầu ra.
Không báo nó là glyph mới bị mất hoặc khẳng định đầu ra không có NUL.

### Bản bàn giao cuối — Python 3.12.15

| Chỉ số | Kết quả |
| --- | --- |
| Thời gian toàn tài liệu | **787,74 giây (13 phút 08 giây)** |
| Đoạn đã dịch / có thể dịch | **98/99 (98,99%)** |
| Đoạn được fallback cứu | **12** |
| Đoạn giữ gốc do fit | **1**, heading `3.1. Inception v3` |
| Lỗi marker / dịch vụ | **0 / 0** |
| Trang / canvas | **9/9, giữ nguyên** |
| Glyph toán nguồn được đối chiếu | **428**, không thiếu glyph nào |
| Span vượt canvas / marker lộ | **0 / 0** |
| Trang tham khảo 7 | **Giống nguồn từng pixel**, 140 DPI |
| NUL trích xuất | **1**, cùng font/bbox với NUL có sẵn trong nguồn |
| Hash nguồn trước/sau | Giống nhau |

Đầu ra: [full9-src-vi.pdf](../output/pdf/audit-offline-2026-10-27-python312/full9-src-vi.pdf).
Số đo: [measurement.json](../output/pdf/audit-offline-2026-10-27-python312/measurement.json).
Gate cấu trúc: [pdf-gate.json](../output/pdf/audit-offline-2026-10-27-python312/pdf-gate.json).
SHA-256 đầu ra: `4bc8ee0311b4ecd7e97b9699599a69d97c23528d20b70e0137a3cb3f4eca03ba`.

Đã render và xem contact sheet của cả 9 trang trên Python 3.12. Các ảnh render
giống từng pixel với lần chẩn đoán 3.11 đã đọc ở độ phân giải cao. Bản giao
được dịch lại bằng 3.12, không chỉ sao chép PDF của lần 3.11. Đọc lại toàn bộ
từ cache với HTTP thật bị chặn tái tạo được 98/99 đoạn và đúng 1 lỗi fit trên.
Các PDF, ảnh và log sinh ra được giữ ngoài source control.

## Guardrails cho lần làm tiếp

```yaml
stacks: [python-3.12, pymupdf, pdfminer, onnxruntime, fastapi, react-typescript, electron]
must:
  - use_repository_venv_and_bundled_core
  - preserve_source_hash_page_count_and_canvas
  - validate_formula_style_and_term_markers_before_cache_and_render
  - reject_non_text_or_incomplete_ollama_answers
  - bump_ollama_cache_revision_when_answer_processing_changes
  - mock_model_status_replies_and_backoff_in_unit_tests
  - preserve_reference_pages_and_mixed_page_citations
  - keep_pdf_gutter_offsets_and_bound_visible_canvases
  - run_unittest_pip_check_hard_ruff_smoke_and_viewer_tests
  - render_every_delivered_pdf_page_and_disclose_kept_source_regions
blockers:
  - source_or_existing_user_output_overwritten
  - new_marker_or_glyph_damage
  - output_reported_complete_when_nothing_translated
external_actions: require_user_scope_for_commit_push_merge_tag_release
```

## Nguồn đối chiếu chính thức

- Hình dạng phản hồi và điều khiển suy luận/cache model:
  [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md).
- Sự kiện console hiện hành:
  [Electron webContents](https://www.electronjs.org/docs/latest/api/web-contents).
- Đường dẫn asset tương đối:
  [Vite build](https://v8.vite.dev/guide/build).
- Hai hạn mức Azure khác nhau:
  [bảng giá](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/translator/),
  [service limits](https://learn.microsoft.com/azure/ai-services/translator/service-limits).

## Giới hạn của kết quả

Tỷ lệ đoạn không bao gồm những vùng được bảo toàn có chủ đích (tham khảo,
thuật toán, một số nhãn bảng/footnote). Nó không chứng minh toàn tài liệu đã
được dịch hoặc thuật ngữ khoa học đều đúng. Bản đo còn dùng tên “Inception
Score” không thống nhất; TranslateGemma còn dịch một số chỗ “generative models”
thành “mô hình sinh học”. Thuật ngữ trong prompt dự phòng chỉ tác động những
đoạn tới qwen, không sửa mọi câu của model chính. Cần người có chuyên môn đọc
lại hoặc chạy với glossary phù hợp trước khi dùng chính thức. Không thay đổi
bảo toàn công thức chỉ để tăng tỷ lệ dịch.

Chưa build bộ cài, kiểm tra macOS/Android, gọi Azure/Google thật hoặc ký/phát
hành. Thay đổi chỉ nằm trong worktree `feature/offline-engine`, chưa tích hợp
vào nhánh đang mở trong IDE.
