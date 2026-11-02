# Phase 5 — Technical verification summary

Status: `technical_verified`; Git persistence: `pending_user_scope`.

## Delivered

- Manifest v2 có common/per-profile, edition lite chỉ fast, runtime compatibility
  và dependency closure; parser v1 giữ nguyên. Profile hỏng độc lập không khóa
  profile tốt, common/schema/path sai vẫn fail closed.
- Snapshot Windows local cho RAM, GPU/VRAM, CPU và disk; TTL 5 giây, GPU timeout
  3 giây, async wrapper và DTO không UUID/serial/path/telemetry.
- EffectivePolicy bất biến, key ổn định không chứa raw free-memory; RTX3050 4 GB
  chỉ tạo ứng viên fast 2K trước. Device check nền dedupe, tối đa hai policy,
  60 giây/probe, kiểm tra cả rescue và chỉ điều khiển worker do app sở hữu.

## Evidence

- Gói v1 thật 21,23 GB: 1.017/1.017 tệp valid, ba profile giữ nguyên.
- 55 test trọng tâm đạt; full suite 449/449 trong 121,525 giây.
- `pip check`, hard Ruff và `git diff --check` đạt.
- Probe thật fast/GPU/4K trên máy phát triển đạt; log `tmp/p5-t3-real-probe-2.log`.
- Máy phát triển RTX3060/32 GB chỉ là smoke; laptop RTX3050 thật vẫn chờ Phase 7.

## Remaining gates

Phase 6 phải truyền policy bất biến qua job/cache, tạo lite/full pack, import local
và tích hợp API/UI. Không ghi PASS/tag vì chưa có Git persistence scope.
