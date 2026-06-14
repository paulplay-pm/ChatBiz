# V4 sso-and-canvas-e2e-fix — Design

> **Schema:** superpowers-bridge
> **依赖:** `brainstorm.md` §1 决策链 + `proposal.md` 5 capability
> **Source of truth:** docs/architecture.md + docs/prd.md + design doc

## Context

V3 (`frontend-product-shell`) 11/11 task 完成,14-gate verify 全 PASS,merge 到 main `a742755`。V3 把 portal/canvas/admin 三前端对齐 `docs/prototype.html` 9 张目标图。V4 续接:

1. **canvas e2e 7+1 失败** 修复(V1 baseline 0 回归,`canvas-tsc-health` 已治 tsc)
2. **SSO 集成**(MVP 企微扫码最小实现,5 spec 锁定完整契约 v0/v1/v2 落地时间)
3. **5 业务 spec 增量**(`sso-integration` + `chatflow-runtime` + `mcp-tool-registry` + `manual-approval-flow-runtime` + `audit-isolation-prod-readiness`)
4. **`canvas-auth` spec Modify** 加 SSO 路径

## Goals

- **G1** canvas e2e 7+1 全绿,补 docker compose test stack
- **G2** portal LoginPage 加 SSO 按钮,dev IM mock 端点完整,e2e 可验证
- **G3** 5 spec + 1 modify spec 落地 `openspec/specs/`,通过 `openspec schema validate`
- **G4** V4 archive + 14-gate verify 全 PASS

## Non-Goals

- 真实企微 webhook 联调 / SAML / Keycloak container
- 任何后端 Python 代码
- `docs/architecture.md` 修改
- Critical path 1/3/4 实际跑通(spec only,V5+ 真实实现)

## Decisions

### D1: canvas e2e 修复策略 = 修协议,不改 NodePanel 架构

- **NodePanel** 14 个 draggable item 加 `data-node-type="workflow/agent/..."` 属性
- **CanvasPage.onDrop** 解析 `dataTransfer.getData('application/chatbiz-node')` 协议
- **e2e/canvas-connection.spec.ts** 改用 `data-node-type` 查找,移除硬编码索引
- **e2e/canvas-edge-deletion.spec.ts** 同上 + 改 `items[7]` → `data-node-type="code"`
- **e2e/node-schema.spec.ts** mock `/api/nodes` 响应体对齐真 schema(14 type + I/O 字段)
- **e2e/paul-monthly-report.spec.ts** 路径 `/workflows` → `/api/v1/workflows`,mock 返 uuid
- **eng-review 一致**: `Quality #1` Node Contract codegen 不动,V4 只 mock 14 type,codegen 留 V5

### D2: SSO dev IM mock 端点 = 选项 B(走 fetch + mock page)

- 流程:`/api/auth/sso/wechat/initiate` → 返 `{ qr_url: '/sso-mock-im?token=xxx' }` → 弹窗跳 `/sso-mock-im` → 用户点"确认登录" → `/api/auth/sso/wechat/callback?token=xxx` → 返 `{ jwt, refresh, expires_in }` → portal state
- **dev IAM** `/api/auth/login` 加 `?via=wechat-scan` 参数
- **理由**: 接近真实企微扫码流程,e2e 可完整跑
- **portal LoginPage** 视觉:沿用 V3 LoginPage,加 "企业扫码登录" 按钮在 username/password 表单下方

### D3: 5 spec 落地策略 = 一次写 5,每 spec 1 个核心 Requirement + 2-3 Scenario

- 每个 spec 1-2 个 Requirement,每 Requirement 3 个 Scenario
- 不写 Requirement chain(spec 内 Requirement 之间不强依赖)
- 5 spec 全部用 superpowers-bridge 模板(Requirement `SHALL/MUST` + `#### Scenario: WHEN/THEN`)
- `canvas-auth` Modify 加 1 个 SSO 路径 Requirement(2 个 Scenario)

### D4: SSO spec 三档落地时间锁定

- **v0 (MVP)**: 企微扫码(本 spec 详细,本次落地 dev mock)
- **v1 (V1.0)**: OIDC(本 spec 占位,标 `[FUTURE-IMPLEMENTATION]`)
- **v2 (V1.5)**: SAML(本 spec 占位,标 `[FUTURE-IMPLEMENTATION]`)

### D5: 依赖 web-integration-test-suite change

- T1 跑前确认 web-integration-test-suite 已 apply
- 若没 apply:T5 拆 task,先把 web-integration-test-suite apply 完
- compose test stack 文件已存在,V4 不写新 compose

## Architecture

### 关键模块流

```
[portal LoginPage]
  ↓ click "企业扫码登录"
[fetch /api/auth/sso/wechat/initiate]
  ↓ return { qr_url: '/sso-mock-im?token=xxx' }
[弹窗 → SsoMockImPage]
  ↓ click "确认登录"
[fetch /api/auth/sso/wechat/callback?token=xxx]
  ↓ return { jwt, refresh, expires_in }
[portal state: authenticated]
  ↓ navigate to /portal/
```

### 数据流 (canvas e2e 修复)

```
[NodePanel item] --data-node-type="agent"--> drag
  ↓
[CanvasPage onDrop] --dataTransfer.getData('application/chatbiz-node')--> parse
  ↓
[rfNodes state] ← new node
  ↓
[react-flow render] → e2e verify .react-flow__node count
```

### 错误处理

- **canvas e2e 失败** = T1 baseline 重跑后精确定位
- **SSO mock fetch 失败** = LoginPage 弹 toast + 重试按钮
- **5 spec 自检失败** = T10 子 task 拆分,逐个验证
- **14-gate 不全 PASS** = 卡哪条修哪条,不跳过

## Risks

- **R1**: T10 高密度(5 spec × Requirement × Scenario),超时风险 → 拆 5 子 task,每 spec 单独 verify
- **R2**: web-integration-test-suite 未 apply → T5 拆 task
- **R3**: V4 期间 main 推进 → rebase 风险低,V3 archive 后无重要推进
- **R4**: portal LoginPage 视觉对齐 prototype #1 → 需保留 V3 既有视觉,加按钮不破坏布局
- **R5**: dev IM mock 端点跟未来真实企微端点兼容性 → spec 锁定 path/query/response schema,实现按 spec

## Migration

- 无数据迁移(V4 是 spec + 最小前端实现,无后端变更)
- 无 UI 迁移(V3 视觉不动,只加 SSO 按钮)
- 端口 / compose 不动

## Open Questions (V4 期间可能 surface)

- **Q1**: T5 跑通后,canvas e2e 是不是要新增 critical path 100% spec 对齐 eng-review `Test #2`?—— 暂列 P2,V4 不做
- **Q2**: T12 SSO 按钮的视觉位置(spec `sso-integration` 锁 vs portal 原型图 #1)?—— V4 选原型图位置(在 username/password 表单下方),但留 design review 余地
- **Q3**: V4 完成后,V5 优先级(SSO 真实联调 / canvas codegen / credential management 实现 / 其他)?—— 留 retrospective 决定

## 15 task 速览(详见 tasks.md)

```
T1  web/canvas install + baseline 跑
T2  确认 canvas-tsc-health 合并
T3  NodePanel data-node-type + CanvasPage.onDrop 协议对齐 + 2 spec 修
T4  node-schema + paul-monthly-report e2e mock 协议对齐 v1 API
T5  apply web-integration-test-suite + compose test stack + 3 integration e2e
T6  canvas 完整 playwright 跑最终 baseline
T7  brainstorm.md(本 change 已完成)
T8  proposal.md(本 change 已完成)
T9  design.md(本 change)
T10 5 spec 落地(sso-integration + chatflow-runtime + mcp-tool-registry
    + manual-approval-flow-runtime + audit-isolation-prod-readiness)
T11 tasks.md(本 change)
T12 portal LoginPage SSO 按钮 + dev IM mock + SsoMockImPage
T13 canvas-auth spec Modify 追加 SSO 路径 + dev IAM /api/auth/login?via=wechat-scan
T14 14-gate verify (8 vitest / 5 playwright / 3 tsc / 4 vite build / 2 nginx curl)
T15 archive V4 change
```
