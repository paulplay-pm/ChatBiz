# V4 sso-and-canvas-e2e-fix — Brainstorm

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:brainstorming
> **Schema:** superpowers-bridge (中文 + 严格测试/审计/标签规则)
> **Base branch:** `worktree-sso-and-canvas-e2e-fix`(基于 V3 merge `a742755`)
> **Source design 引用:** `docs/architecture.md` + `docs/prd.md` + `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md`

## 0. 背景

V3 (`frontend-product-shell`) 已完成 11/11 task,14-gate verify 全 PASS,merge 到 main `a742755`。V3 留下 3 类待办:

1. **canvas e2e 7+1 失败** —— V1 baseline 已知问题,0 回归(`canvas-tsc-health` 已治 tsc + Element|undefined,运行时剩脆点 + 缺 compose test stack)
2. **SSO 集成** —— design doc 推 V1.0 完整 SSO;`system-management` spec MUST 写 MVP 企微扫码;`canvas-auth` spec 提"production 接 Keycloak"是空头承诺
3. **业务 spec 缺口** —— 5 个 design doc / eng-review 12 finding 关联的能力无 openspec spec

V4 = 同时处理这 3 类,边界:**前端为主 + 最小 SSO 集成 + 5 spec 落地**。

## 1. 决策链(locked-in,不再重开)

### D1: SSO 范围 = Spec + 最小实现(企微扫码 mock)

- **理由**: `system-management` MUST 优先级 > design doc V1.0 推延
- **范围**:
  - 写 `openspec/specs/sso-integration/spec.md`(P0,完整 OIDC + 企微 + SAML 三档,标 v0/v1/v2 落地时间)
  - canvas-auth spec 追加 SSO 回跳 + token 兑换 + refresh 契约(Modify)
  - portal LoginPage 加 "企业扫码登录" 按钮 + 假 mock IM 弹窗
  - dev IAM 端点 `/api/auth/login` 加 `?via=wechat-scan` 参数路径
  - 后端 0 行,全部前端 + mock 数据
- **不在 V4 做**: 真实企微 webhook 联调;SAML IdP metadata 解析;Keycloak container 起服务(留 V5+)

### D2: 截止线 = Production-ready(走完 apply + 14-gate)

- 跟 V3 一致节奏:5 artifact → 13 task → 14-gate verify
- 预计 2-3 session(每 session 4-5 task)
- T10 14-gate verify 包含 canvas playwright 7+1 全绿(前提:compose test stack 起来)
- archive 时机 = 14-gate 全 PASS

### D3: 5 个 business spec 全做

| # | spec 名 | 优先级 | 命中 eng-review |
|---|--------|-------|---------------|
| 1 | `sso-integration` | P0 | (新) + `system-management` MUST 补完 |
| 2 | `chatflow-runtime` | P0 | `Arch #4` + critical path 1 (paul 月报) |
| 3 | `mcp-tool-registry` | P0 | `Arch #5` + critical path 4 (插件降级) |
| 4 | `manual-approval-flow-runtime` | P0 | `Arch #6` + critical path 3 (审批续接) |
| 5 | `audit-isolation-prod-readiness` | P1 | `Arch #1` + `Quality #3` (4 错误边界) |

## 2. canvas e2e 7+1 失败根因(Plan agent scoping 报告)

| # | spec | 真因 | V4 修法 |
|---|------|------|---------|
| 1 | `e2e/auth.spec.ts` dev login | env-dependent (vite dev server 启动超时) | T1 重跑 baseline 确认 |
| 2 | `e2e/canvas-connection.spec.ts` drag connect | bug-or-missing-impl (onConnect 写 rfEdges 协议不对) | T3 改 NodePanel 加 `data-node-type` + CanvasPage.onDrop 协议对齐 |
| 3 | `e2e/canvas-edge-deletion.spec.ts` delete edge | bug-or-missing-impl (`items[7]` 硬编码脆点) | T3 同上 + 改测试用 data-type 查找 |
| 4 | `e2e/node-schema.spec.ts` 14 node types | env-dependent (vite dev + 空断言) | T4 mock `/api/nodes` 真返 14 type,前端 `useNodeSchema` 真消费 |
| 5 | `e2e/paul-monthly-report.spec.ts` create + edit | env-dependent (POST `/workflows` v1 API mock 不匹配) | T4 改路径 `/api/v1/workflows` + mock 返 uuid |
| 6 | `e2e/integration/paul-monthly-report.spec.ts` SPA loads through nginx | missing-impl (跟 web-integration-test-suite change 重叠) | T5 apply web-integration-test-suite + 重跑 |
| 7 | `e2e/integration/paul-monthly-report.spec.ts` 401 for unauth | env-dependent (compose test stack 未起) | T5 起 compose test + 重跑 |
| 8 | `e2e/integration/paul-monthly-report.spec.ts` bearer token | env-dependent (同上) | T5 同上 |

**根因分层**:
- **A. 脆点** (T3): 2 个 e2e (canvas-connection + canvas-edge-deletion) 协议不对齐
- **B. vite mock 行为** (T4): 2 个 e2e (node-schema + paul-monthly-report) mock 响应体跟实际消费不匹配
- **C. env-dependent** (T5): 3 个 integration e2e 等 docker compose test stack

**前置任务**: T1 = `web/canvas` `pnpm install` + 重跑 baseline 7+1 取真实结果
**前置任务**: T2 = 确认 `canvas-tsc-health` change 是否已合并;若没合,rebase + 重跑

## 3. SSO 矛盾 surface

| 文档 | 锁定 | V4 处理 |
|------|------|---------|
| `design doc` line 212 + 335 | "跨平台 SSO/SAML/OIDC V1.0;MVP 用企微/钉钉扫码" | D1 已选:MVP 企微扫码先做 |
| `system-management` MUST | "MVP 阶段 MUST 集成企微/钉钉扫码;SSO MUST 跳过密码" | V4 满足 MUST,补完 sso-integration spec |
| `canvas-auth` spec | "production 接 Keycloak 时只改 `/api/auth/login` 内部实现" | V4 在 canvas-auth 追加 SSO 路径(回跳 + token 兑换 + refresh),**不**接 Keycloak,只声明契约 |

**矛盾未彻底解决**(留给 design doc follow-up 单独 change):
- design doc 没明确"企微扫码 = 走 IM OAuth 还是 自建 IM 二维码"
- `sso-integration` spec V4 落 v0 契约,**不**在 V4 内部解决矛盾,只在 spec 顶部加 `[FUTURE-IMPLEMENTATION]` 引用 design doc 矛盾

## 4. 13 task outline (跟 V3 一样 8-stage 流程)

| # | Task | 类型 | 验证配对 | 估时 |
|---|------|------|---------|------|
| T1 | `web/canvas` install + baseline 跑 | 验证 | T1-self | 30min |
| T2 | 确认 canvas-tsc-health 合并 | 验证 | T2-self | 15min |
| T3 | NodePanel `data-node-type` + CanvasPage.onDrop 协议对齐 | 编码 | T3-verify:重跑 2 spec | 2h |
| T4 | node-schema + paul-monthly-report e2e mock 协议对齐 v1 API | 编码 | T4-verify:重跑 2 spec | 2h |
| T5 | apply web-integration-test-suite + docker compose test stack + 3 integration e2e | 编码+验证 | T5-verify:重跑 3 spec | 2h |
| T6 | canvas e2e 7+1 全绿后,跑 canvas 完整 playwright 取最终 baseline | 验证 | T6-self | 30min |
| T7 | 写 `brainstorm.md`(本文件) | 文档 | T7-verify:`openspec status` | 30min |
| T8 | 写 `proposal.md`(3 capability + 5 spec 候选 + SSO 矛盾 surface) | 文档 | T8-verify:`openspec schema validate` | 1h |
| T9 | 写 `design.md`(e2e 7+1 根因 + SSO v0 + 5 spec 触发关系) | 文档 | T9-verify:自检 8 章节齐 | 1h |
| T10 | 写 5 个 spec(SSO + chatflow-runtime + mcp-tool-registry + manual-approval-runtime + audit-isolation-prod-readiness) | 文档 | T10-verify:SHALL/MUST + Scenario 齐全 | 2h |
| T11 | 写 `tasks.md`(把 T1-T10 拆 apply 任务) | 文档 | T11-verify:任务粒度 + 配对验证 | 1h |
| T12 | portal LoginPage 加 "企业扫码登录" 按钮 + dev IM mock 弹窗 | 编码 | T12-verify:vitest | 2h |
| T13 | canvas-auth spec Modify 追加 SSO 路径 + dev IAM `/api/auth/login?via=wechat-scan` 实现 | 编码+文档 | T13-verify:vitest + spec 自检 | 2h |
| T14 | 14-gate verify(8 vitest / 5 playwright / 3 tsc / 4 vite build / 2 nginx curl) | 验证 | T14-verify:14-gate 全 PASS | 1h |
| T15 | archive V4 change | 文档 | T15-verify:archive 目录齐 | 15min |

**总任务数**: 15 (vs V3 11,V4 多 4 个因 spec 数 +1 / 编码 task +1 / 14-gate 项多)
**总耗时**: 2.5-3 session
**风险 task**: T3(协议对齐) / T5(apply web-integration-test-suite 的边界) / T10(5 spec 高密度)

## 5. Non-goals(V4 显式不做)

- 真实企微 webhook 联调
- 真实 SAML IdP metadata 解析
- Keycloak container 起服务
- 任何 `services/<backend>/app/` Python 代码(V4 是前端 + spec 为主)
- docs/architecture.md 修改(SSO 矛盾 surface 后,留 design doc follow-up)
- Critical path 1/3/4 的 100% 实际跑通(只 spec 落地;实际跑通 = V5+ apply 后)

## 6. 与 12 个 eng-review 锁定决策的符合性

- **Arch #1** (egress 强制点): 不动,只 audit-isolation-prod-readiness spec 补 LLM stub + Redis HA
- **Arch #4** (Chatflow 共享 StateGraph): chatflow-runtime spec 落契约
- **Arch #5** (MVP MCP): mcp-tool-registry spec 落契约
- **Arch #6** (人工审批): manual-approval-flow-runtime spec 落契约
- **Quality #1** (Node Contract codegen): V4 不动,T4 只 mock 14 type,等 V5 codegen
- **Quality #3** (4 错误边界): audit-isolation-prod-readiness spec 补
- **Test #2** (critical path 100%): 4 个 critical path 在 5 spec 里有 1:1 对应
- **0 架构变更**: ✅
- **0 后端 API 变更**(0 行 Python): ✅
- **0 端口变更**: ✅
- **0 docker compose 变更**(用现有 test stack): ✅ (前提是 web-integration-test-suite 已 apply)

## 7. 风险与决策点

### R1: web-integration-test-suite 是否已 apply

- 当前 main 上 openspec/changes/ 有 `web-integration-test-suite/` 目录(untracked 还是 active?需 T2 确认)
- 若**没 apply**:T5 风险大,可能要把 web-integration-test-suite 也作为 V4 子 task apply 进来
- 若**已 apply**:T5 只需要确认 compose 文件 + 起服务

### R2: 5 spec 落地的 spec.md 模板一致性

- V3 用了 superpowers-bridge 模板(Requirement + Scenario 形式)
- V4 5 spec 也要对齐,**不**在 V4 重写 schema
- 高密度文档,T10 拆 5 个子 task 风险

### R3: SSO dev IM mock 端点设计

- 选项 A: portal LoginPage 直接渲染假 IM 弹窗(无网络请求)
- 选项 B: portal LoginPage 调 `/api/auth/sso/wechat/initiate` → 返 mock QR code url → 假 IM 页面 `/sso-mock-im?token=xxx` → 用户点"确认登录" → 调 `/api/auth/sso/wechat/callback` → 拿 JWT
- V4 选 B(更接近真实企微扫码流程,e2e 友好)

### R4: V4 期间 portal LoginPage e2e 也要更新

- portal-flow.spec.ts 现有 2 case 不涉及 SSO,V4 不动
- T12 加新 e2e case:portal LoginPage 看到 "企业扫码登录" 按钮

### R5: V4 期间 main 推进

- V4 worktree 基于 `a742755` 起步,V4 apply 期间 main 可能又推进(其他 change merge)
- V4 archive 完可能需要 rebase,或 fast-forward merge
- 风险可控,V3 archive 后已显示无重要 main 推进

## 8. 待 V4 期间用户裁决的潜在 Q

- Q1: T5 跑通后,canvas e2e 是不是要**新增** critical path 100% spec 来对齐 eng-review Test #2?(暂列 P2,V4 不做)
- Q2: T12 SSO 按钮的视觉位置(spec `sso-integration` 锁 vs portal 原型图 #1)?
- Q3: V4 完成后,V5 优先级(SSO 真实联调 / canvas codegen / credential management 实现 / 其他)?

## 9. 关联引用

- [[main-design-20260609-230548]]: eng-review 12 finding 锁定文档
- [[frontend-product-shell-design]]: V3 design doc,V4 续接
- [[canvas-tsc-health]]: 前置 change,可能已 merge
- [[web-integration-test-suite]]: 依赖,T5 之前确认状态
- [[system-management]] spec: SSO MUST 出处
- [[canvas-auth]] spec: V4 Modify 加 SSO 路径
- docs/architecture.md §4.3.5: 企业安全
- docs/prd.md line 861 (SY-019): SSO 集成 P1
- docs/prd.md line 1438-1453: 系统配置 SSO tab
