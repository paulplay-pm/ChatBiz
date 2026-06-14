# V4 sso-and-canvas-e2e-fix — Proposal

> **Schema:** superpowers-bridge
> **Base branch:** `worktree-sso-and-canvas-e2e-fix`(基于 V3 merge `a742755`)
> **Source design:** docs/architecture.md + docs/prd.md + ~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md
> **决策链:** 见 `brainstorm.md` §1(D1 SSO MVP / D2 production-ready / D3 5 spec 全做)

## Why

V3 (`frontend-product-shell`) 11/11 task + 14-gate verify 全 PASS,merge 到 main `a742755`,把 portal/canvas/admin 三前端对齐了 `docs/prototype.html` 9 张目标图。V3 留下 3 类待办:

1. **canvas e2e 7+1 失败** —— V1 baseline 已知 0 回归问题(`canvas-tsc-health` 已治 tsc + Element|undefined,运行时剩脆点 + 缺 compose test stack)
2. **SSO 集成** —— design doc 推 V1.0 完整 SSO;`system-management` MUST 写 MVP 企微扫码;`canvas-auth` spec 提"production 接 Keycloak"是空头承诺
3. **业务 spec 缺口** —— 5 个 design doc / eng-review 12 finding 关联的能力无 openspec spec

V4 = 同时处理这 3 类,边界:**前端为主 + 最小 SSO 集成 + 5 spec 落地**。这是从"前端形态"过渡到"运行时契约"的关键转折点:V3 锁定 UI,V4 锁定运行时边界,为 V5 真实后端实现铺路。

## What Changes

### 5 个新增 capability

#### 1. `sso-integration`(P0,新)

SSO IdP 接入的完整契约:企微扫码 v0(本次落地,dev IM mock)+ OIDC v1(V1.0)+ SAML v2(V1.5)。含 admin SSO 配置页契约 + Keycloak/IM callback handler 契约 + JWT 兑换/refresh + JWKS 端点契约 + `canvas-auth` spec 追加 SSO 回跳路径。

#### 2. `chatflow-runtime`(P0,新)

Chatflow 的后端 runtime 契约:`POST /workflows/:id:run?mode=chatflow` + `X-Session-Id` thread 续接 + LangGraph Checkpointer ↔ PostgreSQL + SSE `node_completed` / `node_pending` 事件 schema。当前 `canvas-chatflow` spec 仅有 UI 契约,缺 backend runtime 契约。

#### 3. `mcp-tool-registry`(P0,新)

MCP server 注册/发现/路由/health-check/凭证注入/降级的统一契约。当前已有 3 个独立 spec(mcp-filesystem-server / mcp-fetch-server / mcp-postgres-server),缺统一的"registry" spec。对齐 eng-review `Arch #5`(MVP MCP 集成)+ `Test #2` critical path ④(插件加载失败降级)。

#### 4. `manual-approval-flow-runtime`(P0,新)

人工审批 runtime 后端契约:`POST /approvals/:id:resume?decision=approved|rejected` + LangGraph `interrupt()` ↔ PostgreSQL checkpointer 序列化 + 通知(企微 webhook)+ 24h timeout + escalation + approver 重入。对齐 eng-review `Arch #6` + `Test #2` critical path ③(人工审批中断续接)。

#### 5. `audit-isolation-prod-readiness`(P1,新)

audit-and-isolation 网关 P0 强制点已 active(`gateway-egress-enforcement-p0`),V4 补 production readiness:LLM echo stub 集成 + Redis Sentinel HA 配置 + trace-id 跨 service 关联 + 4 错误边界(`SecurityError` / `UserError` / `WorkflowRuntimeError` / 7-class `audit-and-isolation/errors.py`)契约。对齐 eng-review `Arch #1` + `Quality #3` + `Perf #1`(cache/rate-limit/batch)。

### 1 个 Modify capability

#### 6. `canvas-auth` (Modify)

在现有 dev mock IAM + JWT + dev fallback 基础上,**追加 SSO 路径**:回跳 URL 处理 + code → token 兑换 + refresh token 续期 + 401 回 IdP 重登。当前 spec 提"production 接 Keycloak 时只改 `/api/auth/login` 内部实现"是空头,V4 把这条声明具体化。

### 4 个 Modified canvas e2e(非 capability,纯工程)

- `e2e/canvas-connection.spec.ts`: 修协议(NodePanel `data-node-type` + CanvasPage.onDrop 对齐)
- `e2e/canvas-edge-deletion.spec.ts`: 改硬编码 `items[7]` → data-type 查找
- `e2e/node-schema.spec.ts`: 改 mock 响应体让 `useNodeSchema` 真消费 14 type
- `e2e/paul-monthly-report.spec.ts`: 改路径 `/workflows` → `/api/v1/workflows` + mock uuid

### 3 个 integration e2e baseline 验证

- `e2e/integration/paul-monthly-report.spec.ts` 3 case: 依赖 `infrastructure/docker-compose-test.yml` 起 + 走 web-integration-test-suite change apply

### 1 个 portal LoginPage 修改(SSO 最小实现)

- LoginPage 加 "企业扫码登录" 按钮
- 点击 → `/api/auth/sso/wechat/initiate` → 返 mock QR code url
- 弹窗跳假 IM 页面 `/sso-mock-im?token=xxx` → 用户点"确认登录" → `/api/auth/sso/wechat/callback` → 拿 JWT → portal state
- dev IAM 端点 `/api/auth/login` 加 `?via=wechat-scan` 参数路径
- 后端 0 行,前端 + MSW-style mock fetch

## Impact

### 影响的 spec 增量

- **新增 5 个 spec 目录**:`openspec/specs/{sso-integration,chatflow-runtime,mcp-tool-registry,manual-approval-flow-runtime,audit-isolation-prod-readiness}/spec.md`
- **Modify 1 个 spec 目录**:`openspec/specs/canvas-auth/spec.md`(追加 SSO 路径)

### 影响的源码

| 路径 | 类型 | 行数估 |
|------|------|------|
| `web/portal/src/pages/LoginPage.tsx` | Modify | +30 (SSO 按钮 + 弹窗触发) |
| `web/portal/src/data/auth.ts` | New | +50 (SSO mock fetch helper) |
| `web/portal/src/pages/SsoMockImPage.tsx` | New | +60 (假 IM 确认页) |
| `web/portal/tests/pages_SsoMockImPage.test.tsx` | New | +40 |
| `web/portal/tests/data_auth.test.ts` | New | +30 |
| `web/portal/src/router/index.tsx` | Modify | +5 (新 route) |
| `web/canvas/src/components/NodePanel.tsx` | Modify | +5 (data-node-type) |
| `web/canvas/src/pages/CanvasPage.tsx` | Modify | +5 (协议对齐) |
| `web/canvas/e2e/canvas-connection.spec.ts` | Modify | -10 (硬编码改查) |
| `web/canvas/e2e/canvas-edge-deletion.spec.ts` | Modify | -5 |
| `web/canvas/e2e/node-schema.spec.ts` | Modify | -3 |
| `web/canvas/e2e/paul-monthly-report.spec.ts` | Modify | -3 |
| `web/portal/e2e/portal-flow.spec.ts` | Modify | +20 (新 SSO case) |
| `web/portal/src/components/AppLayout.tsx` | Modify | +2 (header 加 SSO 状态) |
| `infrastructure/docker-compose-test.yml` | 验证 | (不写,只起) |

**总估**: ~13 文件改/新建,前端 ~270 行新增 + ~30 行删;后端 0 行。

### 影响的 openspec 流程

- archive 时 5 spec 增量 apply 到 `openspec/specs/`
- `canvas-auth` spec Modify(ADDED Requirements 加 1 个 SSO 路径 Requirement)

## Non-Goals(V4 显式不做)

- 真实企微 webhook 联调
- 真实 SAML IdP metadata 解析
- Keycloak container 起服务
- 任何 `services/<backend>/app/` Python 代码(V4 是前端 + spec 为主)
- `docs/architecture.md` 修改(SSO 矛盾 surface 后,留 design doc follow-up 单独 change)
- Critical path 1/3/4 的 100% 实际跑通(只 spec 落地;实际跑通 = V5+ apply 后)
- 完整 OIDC / SAML 实现(只在 spec 锁定契约,不实现)
- 改动 portal DashboardPage / admin 6 view(V3 已对齐)
- 改动 Sidebar menu(V3 已对齐)

## 与 12 个 eng-review 锁定决策符合性

| Finding | 状态 |
|---------|------|
| Arch #1 egress 强制点 | 不动,只在 spec 补 LLM stub + Redis HA 契约 |
| Arch #2 Node Contract codegen | 不动,V4 只 mock 14 type,codegen 留 V5 |
| Arch #3 4 层记忆 | 不动 |
| Arch #4 Chatflow 共享 StateGraph | chatflow-runtime spec 落契约 |
| Arch #5 MVP MCP | mcp-tool-registry spec 落契约 |
| Arch #6 人工审批 | manual-approval-flow-runtime spec 落契约 |
| Quality #1 Node Contract codegen | 不动 |
| Quality #2 50 paul LLM eval | 不动 |
| Quality #3 4 错误边界 | audit-isolation-prod-readiness spec 补 |
| Test #1 3 层测试 | V4 加 SSO e2e + canvas e2e 修复 |
| Test #2 critical path 100% | 4 critical path 在 5 spec 有 1:1 对应(spec only,V4 不实现 100%) |
| Perf #1 cache/rate-limit | audit-isolation-prod-readiness spec 补 |

**0 架构变更** ✅
**0 后端 API 变更**(0 行 Python)✅
**0 端口变更** ✅
**0 docker compose 变更**(用现有 test stack)✅

## 风险与依赖

### 依赖前置(必须确认)

1. **web-integration-test-suite change 已 apply** —— T5 起 compose test stack 依赖此 change;若没 apply,T5 风险大,可能要把 web-integration-test-suite 也作为 V4 子 task
2. **canvas-tsc-health change 已 merge 到 main** —— V3 merge 包含;确认 `web/canvas/src/vite-env.d.ts` 在 git tree 内

### 风险

- **R1**: T10 写 5 个 spec 高密度,可能超时;拆 5 个子 task
- **R2**: T5 apply web-integration-test-suite 的边界(可能改 compose / nginx 配置)
- **R3**: V4 期间 main 推进(V3 archive 后无重要推进,风险低)
- **R4**: portal LoginPage 改 SSO 按钮的视觉对齐 `docs/prototype.html` 原型图(若视觉差异大,需 design review)
- **R5**: SSO dev IM mock 端点选 B(更接近真实流程,e2e 友好),spec 跟实现一致

## 决策点(已 locked)

| ID | 决策 | 选择 |
|----|------|------|
| D1 | SSO 范围 | **Spec + 最小实现(企微扫码 mock)** |
| D2 | 截止线 | **Production-ready(走完 apply + 14-gate)** |
| D3 | spec 数量 | **全 5 个** |
| D4 | dev IM mock 端点设计 | **选项 B(走 fetch + mock page)**,理由:e2e 友好 + 接近真实流程 |
| D5 | canvas e2e 修复方式 | **修协议 + 改硬编码 + mock 响应体**,不重构 NodePanel |
