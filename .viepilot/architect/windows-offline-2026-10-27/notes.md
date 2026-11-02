---
session_id: windows-offline-2026-10-27
project: PDF Translate Offline Windows
created: 2026-10-27
updated: 2026-10-27
status: design_review
scope_locked: true
workspace_mode: both
---

## decisions
```yaml
decisions:
  - {id: D01, topic: initial_platform, chosen: windows, status: decided}
  - {id: D02, topic: connectivity, chosen: offline_only, status: decided}
  - {id: D03, topic: profiles, chosen: [fast, balanced, quality], status: decided}
  - {id: D04, topic: anonymity, chosen: user_facing_surfaces, status: decided}
  - {id: D05, topic: default_profile, chosen: balanced, status: proposed}
  - {id: D06, topic: delivery, chosen: installer_and_verified_offline_pack, status: proposed}
```

## Coverage
| ID | Tính năng | Phase | Thành phần | Architect | UI |
| --- | --- | --- | --- | --- | --- |
| P1-01 | Chính sách không Internet | 1 | Offline Policy | architecture.html#C02 | Trạng thái cục bộ + lỗi |
| P1-02 | Profile công khai, mapping nội bộ | 1 | Profile Resolver / DTO | apis.html | Ba thẻ mức xử lý |
| P1-03 | Gói dữ liệu và kiểm tra manifest | 1 | Asset Store / Preflight | deployment.html | Thiếu dữ liệu |
| P1-04 | Giữ nguồn và cấu trúc PDF | 1 | PDF Pipeline / Staging | data-flow.html | Hai khung + báo cáo một phần |
| P2-01 | Làm sạch lỗi/API/log người dùng | 2 | Public Error Mapper | apis.html | Lỗi trung tính + mã hỗ trợ |
| P2-02 | Runtime do sản phẩm quản lý | 2 | Worker Supervisor | sequence-diagram.html | Chuẩn bị / sẵn sàng |
| P2-03 | Tiến độ, hủy, đọc song song | 2 | Job Queue / Viewer | user-use-cases.html | Đang xử lý / đã hủy |
| P3-01 | Bộ cài Windows hoàn toàn local | 3 | Installer / Pack Validator | deployment.html | Cài gói từ tệp cục bộ |
| P3-02 | Nghiệm thu egress và ẩn danh | 3 | Integration QA | tech-notes.html | Mọi trạng thái |
| P3-03 | Đo profile và thuật ngữ | 3 | Benchmark / Human review | tech-notes.html | Mô tả mức có bằng chứng |

## tech_stack
```yaml
frontend: Electron / React / TypeScript (existing)
backend: Python 3.12 / FastAPI / local worker
storage: local SQLite cache and filesystem
deployment: Windows single machine, IPC or loopback only
runtime_vendor_mapping: private, not part of public API
```

## erd
```yaml
entities:
  - {name: Job, storage: memory, attributes: [id, profile, status, progress]}
  - {name: ProfileConfig, storage: local_config, attributes: [id, revision]}
  - {name: AssetRecord, storage: local_manifest, attributes: [internal_id, sha256, pack_revision]}
  - {name: CacheEntry, storage: sqlite, attributes: [source_key, translation, processing_revision]}
relationships:
  - {from: ProfileConfig, to: Job, type: one_to_many}
  - {from: ProfileConfig, to: AssetRecord, type: one_to_many}
```

## use_cases
```yaml
actors: [local_user]
scenarios: [first_install_without_internet, translate, missing_assets, cancel, partial_result, local_update]
```

## apis
```yaml
style: local_REST
authentication: per_session_token
public_profile_ids: [fast, balanced, quality]
endpoints: ["GET /api/health", "GET /api/capabilities", "POST /api/jobs", "GET /api/jobs/{id}", "POST /api/jobs/{id}/cancel", "GET /api/jobs/{id}/result"]
exclude: [model_identity, vendor_identity, raw_worker_errors, engine_urls, pull_commands]
```

## admin
```yaml
applicable: false
rationale: single_user_local_desktop_no_admin_panel_or_roles
```

## content
```yaml
cms_applicable: false
rationale: PDF processing is not a publishing or CMS workflow
```

## entity_mgmt
```yaml
admin_crud_applicable: false
rationale: runtime jobs and private cache do not require an admin CRUD dashboard
```

## user_data
```yaml
accounts: false
cloud_sync: false
source_mutation: forbidden
data_locations: [source_file, private_staging, output_file, private_cache]
support_report: local_opt_in_and_sanitized
retention_changes: require_separate_design
```

## deployment
```yaml
target: windows
first_run_offline: required
distribution: local_installer_and_full_verified_pack
runtime_network: IPC_or_loopback_only
asset_missing: fail_closed
automatic_network_update: disabled
```

## open_questions
- Sizing/minimum RAM/VRAM and package split need measurement; no numerical claim yet.
- Final worker embedding and redistribution feasibility need verification.
- Balanced is the proposed default; user may change it during review.

## Diagram rendering
Native inline SVG and local Mermaid source sidecars. No CDN or remote font.
This overrides the generic skill's CDN example because the user requires an entirely offline design.
The diagrams are design intent, not evidence that runtime egress is already blocked.

## Review actions
Each card has a stable ARCH ID. Copying APPROVE/EDIT is only review text;
it does not approve another page, change the product or mark implementation complete.

## Pages inventory
| Page | Purpose |
| --- | --- |
| index.html | Overview and UI preview entry |
| architecture.html | Kiến trúc hệ thống |
| data-flow.html | Luồng dữ liệu |
| decisions.html | Các quyết định |
| tech-stack.html | Nền tảng kỹ thuật |
| tech-notes.html | Rủi ro & câu hỏi |
| feature-map.html | Tính năng & giai đoạn |
| erd.html | Dữ liệu cục bộ |
| user-use-cases.html | Tình huống sử dụng |
| sequence-diagram.html | Trình tự xử lý |
| deployment.html | Đóng gói Windows |
| apis.html | Hợp đồng API |
| design.html | Ngôn ngữ thiết kế |
