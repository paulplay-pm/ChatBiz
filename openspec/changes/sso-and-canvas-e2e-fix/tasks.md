# V4 sso-and-canvas-e2e-fix — Tasks

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans
> **Goal:** V3 续接 — canvas e2e 7+1 全绿 + SSO 最小实现(企微扫码 mock)+ 5 spec 落地 + canvas-auth Modify + 14-gate verify + archive
> **Source design doc:** `openspec/changes/sso-and-canvas-e2e-fix/{brainstorm,proposal,design}.md`
> **Base branch:** `worktree-sso-and-canvas-e2e-fix`(基于 V3 merge `a742755`)

## 1. canvas e2e 前置 + baseline

- [x] 1.1 `cd web/canvas && pnpm install` 装 vite + playwright + 依赖 → Done 1.1s
- [x] 1.2 跑 `pnpm exec playwright test` 取真实 baseline → **7 fail / 1 pass**(与 V3 T8 + Plan agent 报告一致,0 回归)
  - fail 7:auth / canvas-connection / canvas-edge-deletion / 2 integration / node-schema / paul-monthly-report
  - pass 1:integration paul-monthly-report SPA loads through nginx(5173 容器在跑)
- [x] 1.3 确认 `web/canvas/src/vite-env.d.ts` 在 git tree → `git ls-files` 确认 ✓
- [x] 1.4 确认 `openspec/changes/web-integration-test-suite/` 已 8/8 artifact complete + `infrastructure/docker-compose-test.yml` 存在 → 满足 T4 依赖
- [x] 1.5 Commit: 验证任务,无源码改动(安装产物在 node_modules 不进 git)

## 2. NodePanel + CanvasPage 协议对齐 + 2 spec 修

- [x] 2.1 改 `web/canvas/src/components/canvas/NodePanel.tsx`:14 draggable item 加 `data-node-type="<node_type>"` 属性
- [x] 2.2 改 `web/canvas/src/pages/CanvasPage.tsx`:onDrop 解析 `dataTransfer.getData('application/chatbiz-node')` → **无需改**(已对齐,返回 type 字符串)
- [x] 2.3 改 `web/canvas/e2e/canvas-connection.spec.ts`:硬编码 `items[2]=LLM` `items[5]=code` → `[data-node-type="llm"]` / `[data-node-type="code"]`
- [x] 2.4 改 `web/canvas/e2e/canvas-edge-deletion.spec.ts`:同上 + `items[7]` → `[data-node-type="http"]`
- [x] 2.5 跑 `pnpm exec playwright test e2e/canvas-connection.spec.ts e2e/canvas-edge-deletion.spec.ts` → 仍 2/2 fail(原因:playwright webServer 期望 pnpm dev 起 5173 canvas dev server,当前 5173 跑 nginx 容器;placeholder '任意非空 username' 找不到)。**协议改对了**,完整跑通待 T4 起 compose test stack 后再验证
- [x] 2.6 跑 `pnpm exec tsc --noEmit` 在 canvas → EXIT 0(ui/primitives/Toast 5 错误是 ui node_modules 缺,非阻塞)
- [x] 2.7 Commit: `fix(canvas): NodePanel data-node-type + 2 e2e 协议对齐` → `71f07cd`

## 3. node-schema + paul-monthly-report e2e mock 协议对齐 v1 API

- [x] 3.1 改 `web/canvas/e2e/node-schema.spec.ts`:mock `/api/nodes` 响应体对齐真 schema(14 type + I/O 字段)—— 加 `input_schema` + `output_schema` 字段
- [x] 3.2 改 `web/canvas/e2e/paul-monthly-report.spec.ts`:路径保持 `/workflows`(V3 现状,v1 API 迁移是 chatflow-runtime spec 范围),mock 返 uuid `b3d4e5f6-...` 而非字面量 `paul-monthly`
- [x] 3.3 跑 `pnpm exec playwright test e2e/node-schema.spec.ts e2e/paul-monthly-report.spec.ts` → 仍 2/2 fail(同 T2 环境问题,playwright webServer 期望 dev 5173)
- [x] 3.4 跑 `pnpm exec tsc --noEmit` 在 canvas → EXIT 0
- [x] 3.5 Commit: `fix(canvas): 2 vite e2e mock 协议对齐 v1 API` → `41fb997`

## 4. integration e2e + compose test stack

- [x] 4.1 确认 `infrastructure/docker-compose-test.yml` 包含 workflow-engine + audit-isolation + postgres + redis → 文件存在,使用 dev stack 同样的镜像
- [x] 4.2 docker compose 启动方式:**用现有 dev stack 共享**(postgres/redis/mcp/audit-isolation/workflow-engine/credential 已在跑),V4 **不** 起 test stack(避免端口冲突)
  - **关键修复**:`chatbiz-web:v3` 容器**没**加 `--network chatbiz-net`,导致 nginx → workflow-engine DNS 解析失败,`/workflows` 返 502
  - 修法:`docker rm -f chatbiz-web` + `docker run -d --rm --name chatbiz-web --network chatbiz-net -p 5173:80 chatbiz-web:v3`
- [x] 4.3 跑 `pnpm exec playwright test --config=playwright.integration.config.ts` → **3/3 PASS**
  - ✓ workflows API returns 401 for unauthenticated (13ms)
  - ✓ workflows API accepts bearer token (14ms)
  - ✓ canvas SPA loads through nginx and shows portal (105ms)
- [x] 4.4 验证 nginx 5-path 5173:`/` `/portal/login` `/canvas/` `/admin/` `/workflows`(401)= 4 个 SPA 200 + 1 个 API 401(预期)
- [x] 4.5 Commit: 验证任务,源码无改动;网络修复在 docker 层,记录到 CLAUDE.md 或 operations 文档

## 5. canvas 完整 playwright 最终 baseline

- [ ] 5.1 跑 `pnpm exec playwright test` 在 canvas 期望 8/8 PASS(T2-T4 修复后)
- [ ] 5.2 跑 `pnpm exec vitest run` 在 canvas 期望 32/84 全 PASS(0 回归)
- [ ] 5.3 Commit: `chore(canvas): 8/8 e2e + 32/84 vitest 全绿`

## 6. 5 spec 落地(高密度,每 spec 单独 verify)

- [ ] 6.1 新建 `openspec/changes/sso-and-canvas-e2e-fix/specs/sso-integration/spec.md`(已完成草稿)
- [ ] 6.2 新建 `openspec/changes/sso-and-canvas-e2e-fix/specs/chatflow-runtime/spec.md`(已完成草稿)
- [ ] 6.3 新建 `openspec/changes/sso-and-canvas-e2e-fix/specs/mcp-tool-registry/spec.md`(已完成草稿)
- [ ] 6.4 新建 `openspec/changes/sso-and-canvas-e2e-fix/specs/manual-approval-flow-runtime/spec.md`(已完成草稿)
- [ ] 6.5 新建 `openspec/changes/sso-and-canvas-e2e-fix/specs/audit-isolation-prod-readiness/spec.md`(已完成草稿)
- [ ] 6.6 跑 `openspec schema validate superpowers-bridge` 期望 0 error
- [ ] 6.7 跑 `openspec status --change sso-and-canvas-e2e-fix` 期望 specs artifact status done
- [ ] 6.8 Commit: `docs(openspec): V4 5 spec 落地 (SSO + chatflow + mcp + approval + audit)`

## 7. portal LoginPage SSO 按钮 + dev IM mock

- [ ] 7.1 新建 `web/portal/src/data/auth.ts`:`ssoInitiate()` / `ssoCallback()` / `ssoMockImConfirm()` 三个 fetch helper
- [ ] 7.2 改 `web/portal/src/pages/LoginPage.tsx`:在 username/password 表单下方加"企业扫码登录"按钮
- [ ] 7.3 新建 `web/portal/src/pages/SsoMockImPage.tsx`:假 IM 弹窗,显示 token + "确认登录"按钮
- [ ] 7.4 改 `web/portal/src/router/index.tsx`:加 `/sso-mock-im` 路由
- [ ] 7.5 新建 `web/portal/tests/data_auth.test.ts` 断言 3 helper 函数
- [ ] 7.6 新建 `web/portal/tests/pages_SsoMockImPage.test.tsx` 断言 token 显示 + 确认按钮 + fetch 触发
- [ ] 7.7 跑 vitest 期望 2 文件全 PASS
- [ ] 7.8 跑 `pnpm exec tsc --noEmit` 在 portal 期望 EXIT 0
- [ ] 7.9 改 `web/portal/e2e/portal-flow.spec.ts`:加 SSO e2e case(login → 扫码 → 确认 → 跳 dashboard)
- [ ] 7.10 跑 `pnpm exec playwright test` 在 portal 期望 3+/3+ PASS(V2 baseline + 1 新 SSO)
- [ ] 7.11 Commit: `feat(portal): SSO 企微扫码最小实现 + dev IM mock + e2e`

## 8. canvas-auth spec Modify 追加 SSO 路径

- [ ] 8.1 改 `web/portal/src/api/auth.ts`(若 dev IAM 端点需要):`/api/auth/login` 支持 `?via=wechat-scan` 参数
- [ ] 8.2 改 `web/canvas/src/store/useAuthStore.ts`(若 canvas 也有 auth state):支持 SSO token 注入
- [ ] 8.3 新建 `openspec/changes/sso-and-canvas-e2e-fix/specs/canvas-auth/spec.md`(Modify 增量,已在 6.6 验过)
- [ ] 8.4 跑 tsc + vitest 期望全 PASS
- [ ] 8.5 Commit: `feat(auth): canvas-auth Modify SSO 路径 + dev IAM ?via=wechat-scan`

## 9. 14-gate verify

- [ ] 9.1 8 vitest:portal 40+N / canvas 84 / admin 32 / sso-mock-im 6 / auth 5 / ui N/A
- [ ] 9.2 5 playwright:portal 3 cross-app + 2 portal-flow(含 SSO) / canvas 8 / admin 5
- [ ] 9.3 3 tsc:portal / canvas / admin EXIT 0
- [ ] 9.4 4 vite build:portal ~200KB / canvas ~820KB / admin ~222KB / sso-mock-im-page 0
- [ ] 9.5 2 nginx 7-path curl:`/` `/portal/login` `/portal/sso-mock-im` `/canvas/` `/admin/` `/admin/users` `/health` 全 200
- [ ] 9.6 14-gate 全 PASS,记 commit: `chore(ops): V4 sso-and-canvas-e2e-fix 14-gate verify`

## 10. archive V4 change

- [ ] 10.1 `openspec archive sso-and-canvas-e2e-fix --yes`
- [ ] 10.2 验证 `openspec/changes/archive/2026-06-14-sso-and-canvas-e2e-fix/` 含 5 文件 + 6 specs
- [ ] 10.3 Commit archive + V4 worktree 等合并 main

## 任务统计

- **总任务数**:10 个一级 + ~45 个二级 checkbox
- **总耗时估算**:2.5-3 个 session(每 session 3-4 task)
- **每 task ≤ 2h**:✅ 全部符合(T6 写 5 spec 是高密度,拆 8 个子 step 各自 ≤ 2h)
- **编码配对验证**:✅ T2/T3/T4/T7/T8 每 task 都有 vitest / tsc / playwright 验证
- **不先实现后补测试**:✅ T7 单元测试跟 SSO 实现同 commit

## 与 12 个 eng-review 锁定决策符合性

- 0 架构变更 ✅
- 0 后端 API 变更 ✅
- 0 端口变更 ✅
- 0 新 npm 依赖 ✅
- 0 docker compose 新文件(用现有 test stack)✅
- 仅前端 + spec 形态 ✅
