# Kế hoạch xử lý BUG-009–BUG-013 — 30/10/2026

Trạng thái Phase 1: **partial / technical_verified**. Đã triển khai 6/7 task và xác minh kỹ thuật 5/7; P1-T5 chờ Android SDK/dependencies, P1-T7 chờ Android gate và Git persistence. Runtime giữ nguyên 0.3.0; chưa phát hành 0.3.1. Mục tiêu offline 0.4.0 giữ nguyên.

| Task | Nội dung | Trạng thái | Bằng chứng |
| --- | --- | --- | --- |
| P1-T1 | Baseline và đối chiếu hai checkout | technical_verified | root `feat/domain-glossary@c980d53`, bảo toàn dirty worktree |
| P1-T2 | BUG-009: CORS Electron | technical_verified | preflight `null`; token thiếu/sai/đúng; origin ngoài allowlist |
| P1-T3 | BUG-012: cache marker | technical_verified | cache cũ hỏng bị bỏ qua; đáp án hỏng không được ghi cache |
| P1-T4 | BUG-010: cảnh báo dịch partial | technical_verified | core → job DTO → API → banner UI; zero-translated bị từ chối |
| P1-T5 | BUG-011: đoạn dài Android | implemented, verification_blocked | bỏ `take(5000)`, giữ nguyên nguồn; thiếu platform android-35/dependencies |
| P1-T6 | BUG-013: summary offline | technical_verified | 6 task P4–P5 verified, 6 task P6–P7 planned |
| P1-T7 | Hồi quy tích hợp | partial | desktop gates đạt; Android và Git persistence còn chờ |

Chi tiết: [SPEC](phases/01-audit-bugfix/SPEC.md), [tasks](phases/01-audit-bugfix/tasks/PLAN.md), [summary](phases/01-audit-bugfix/SUMMARY.md).

Viewer liên tục/đồng bộ/Ctrl-wheel/kéo chuột được bảo toàn và frontend build đạt. ENH-002 P6/P7, BUG-007, ENH-001 thuộc backlog riêng. Không commit/push/merge/tag/release/ký hoặc ghi đè PDF.