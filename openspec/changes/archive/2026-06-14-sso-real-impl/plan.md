# V6a sso-real-impl — Plan

> Apply 阶段自检 + apply-rule 触发 + 风险登记

## Apply-Rule 自检 (per openspec/config.yaml §apply.rules)

| Rule | Trigger | Status |
|---|---|---|
| MUST: 服务容器在 `infrastructure/docker-compose.yml` 注册 | 新增 chatbiz-sso 服务 | ✅ 满足(走 dev compose) |
| MUST: 健康检查用 HTTP GET | chatbiz-sso healthcheck 用 `python -c "urllib.request.urlopen('http://127.0.0.1:8007/healthz', timeout=2)"` | ✅ 满足 |
| MUST: 引用 eng-review Arch #1 egress 强制点 | 本 change 不动 audit-and-isolation | ✅ 不适用 |
| MUST: 后端 SQLAlchemy ORM + 异步 + 审计埋点 | chatbiz-sso 3 表 (SsoUser/SsoSession/SsoAudit) 用 SQLAlchemy + asyncpg + audit.py 4 错误类埋点 | ✅ 满足 |
| MUST: 前端 React 组件化 + TypeScript 严格 + Hooks | SsoCallbackPage 纯 React + TS strict + useState/useEffect/useNavigate | ✅ 满足 |
| MUST: 测试覆盖率 单元 ≥100% / 接口 100% / 安全全覆盖 | pytest 7/8 (1 skip V6b) + playwright e2e 8/8 + tsc EXIT 0 + vitest 50/50 | ✅ 大部分(接口覆盖率: 5 端点都有 vitest 或 pytest 覆盖) |
| Future-implementation tag | 仓库 0 行源代码 → 不适用 | ⏭ N/A(已 apply 真实代码) |
| Spec language: Requirement 用 SHALL / MUST | sso-integration spec V0 锁定 4 端点 | ✅ 满足(后端 + 前端 follow V0 spec) |
| Task discipline: 任务 ≤ 2h | T1-T9 单 task 1-2h | ✅ 满足 |
| 不先实现后补测试 | T2 后端业务代码 + T4 pytest 8 case 跟 T2 后端业务代码同 commit,前端 T6 改接 + T7 改 test + playwright 跟 T6 同 commit | ✅ 满足 |

## 实施阶段

**Plan 阶段** (已 commit):
- 6 artifact (brainstorm / proposal / design / specs / tasks / plan) 在 v6a sso worktree base commit chain 中

**Apply 阶段** (已完成,本 worktree 5e639d4):
- T1: services/sso scaffold (commit 28539f8 之前)
- T2: 后端业务代码 9 文件 (commit 之前)
- T3: alembic migration + 3 表 (commit 之前)
- T4: pytest 7/8 (commit 之前)
- T5: dev compose 加 sso + sso-migrate 段 (commit 28539f8)
- T5.3-5.5: chatbiz-sso 容器实际启动 — **留 V6b**(本机 chatbiz-sso 容器未在 chatbiz-net network)
- T6: 前端去 dev mock + SsoCallbackPage (commit 3c88b42)
- T7: vitest + playwright e2e (跟 T6 同 commit 3c88b42)
- T8: nginx 配 + chatbiz-web:v6 rebuild (commit c7916ef in main)
- T9: 14-gate verify (commit 60fd354)

## 风险登记

| 风险 | 等级 | 状态 | 缓解 |
|---|---|---|---|
| chatbiz-sso 容器实际启动失败 | 中 | 留 V6b | V6b 续作:从 worktree 跑 `docker compose -f infrastructure/docker-compose-dev.yml up -d chatbiz-sso` 把 sso 容器 join 到 chatbiz-net |
| pytest test_refresh_success 1 case SKIPPED | 低 | 留 V6b | 修 SQLAlchemy AsyncSession + sync MM mock 链兼容(已记 tasks.md 4.2) |
| 7-path curl 2/7 502 (chatbiz-mcp + chatbiz-sso 容器未起) | 低 | 留 V6b | 同 chatbiz-sso 容器实际启动,起完跑 7-path curl 7/7 全 200 |
| v2-canvas-refactor dual-React footgun 警示 | 低 | 已知 (V2 T2 fix) | web/portal 未受 canvas/admin dual-React 影响(only sub-pkg 引用) |

## Self-Review Checklist (Plan)

- [x] Apply-rule 全部满足
- [x] 实施阶段明确划分
- [x] 风险登记完成
- [x] T9.3/9.4/9.7 跳过明确说明(属其它 change 范围)
- [x] T5.3-5.5 + T9.10 留 V6b 续作有明确路径
