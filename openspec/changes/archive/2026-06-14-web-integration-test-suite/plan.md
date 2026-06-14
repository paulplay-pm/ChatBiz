# web-integration-test-suite Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. apply 阶段按本 plan 跑——agent 应在每个 task 落地前**自行展开** micro-step，不机械照抄。

**Goal:** 建 web 集成测试基础设施（test compose + Playwright 真实链路 + API 集成测试 + admin health E2E + LLM echo stub），让 eng-review **Test #2** 的 4 critical path 中 ① paul 财务月报端到端 推到 100% 覆盖；②③④ 留 spec 扩展点给后续 change 接管。

**Architecture:** 独立 `infrastructure/docker-compose-test.yml`（`--project-name chatbiz-test` 与 production 互斥）起 web（nginx 5173）+ 4 后端 service（credential / workflow-engine / mcp / audit-and-isolation）+ 共享 pg/redis；Playwright 走 nginx `localhost:5173` 统一入口（CLAUDE.md "单端口 5173" 约定）；`web/admin/src/api/health.ts` 改相对路径 `/healthz` + `web/nginx.conf` 加 proxy；`services/audit-and-isolation/app/llm_echo_stub.py` 在 `INTEGRATION_TEST=1` env gating 下注册到 audit-and-isolation 路由表（eng-review Arch #1 兼容，echo stub 必须过 egress 强制点）；`make test-integration` 单命令入口。

**Tech Stack:**
- Docker 24+ / docker compose 2.20+
- Node ≥ 20 / pnpm 10.x
- Python 3.11+（audit-and-isolation 子模块 echo stub）
- Vitest 1（前端 integration runner）
- @playwright/test 1.40（前端 E2E）
- pytest 8（后端 echo stub 单测）
- nginx（web 统一入口，已存在）

---

> **OPT — writing-plans skill fallback**：当前 session skills 列表**未**装载 `superpowers:writing-plans`（与 `admin-bootstrap` retrospective 记录一致）。按 schema `plan.instruction` 提示手写。模式：节级 micro-step 模板 + 关键 task 完整展开，apply 阶段由 subagent-driven-development 自行补全 micro-step。

---

## Phase 1: 基础设施（test compose + Makefile + nginx + LLM echo stub）

### Task 1.1: `infrastructure/docker-compose-test.yml` 7 service 编排

**Files:**
- Create: `infrastructure/docker-compose-test.yml`
- Create: `infrastructure/.env.test.example`（入库）
- Create: `infrastructure/.gitignore` 排除 `infrastructure/.env.test`（如果还没有）

**Step 1**: 写 `docker-compose-test.yml` 框架（7 service 定义，端口与 production 一致，project name 显式声明）
**Step 2**: 加 healthcheck + depends_on.service_composedly_successfully
**Step 3**: 写 `.env.test.example` + `.env.test` 到 gitignore
**Step 4**: 验证：`docker compose -p chatbiz-test config` 退出码 0

### Task 1.2 ★: LLM echo stub

**Files:**
- Create: `services/audit-and-isolation/app/llm_echo_stub.py`
- Modify: `services/audit-and-isolation/app/main.py`（注册 echo router 在 env gating 下）
- Create: `services/audit-and-isolation/tests/test_llm_echo_stub.py`

**Step 1**: 写 `llm_echo_stub.py`（Pydantic schema + async handler + OpenAI 兼容响应 shape）
**Step 2**: 在 `main.py` 加 `if os.getenv("INTEGRATION_TEST") == "1": router.include_router(echo_router)`
**Step 3**: 写单测：3 case（echo 响应 / model 白名单 / 审计埋点），覆盖率 100%
**Step 4**: 验证：`docker compose -p chatbiz-test up audit-and-isolation` + curl `/v1/chat/completions` 返回 ECHO

### Task 1.3 ★: nginx `/healthz` proxy + admin health URL 改相对路径

**Files:**
- Modify: `web/nginx.conf`
- Modify: `web/admin/src/api/health.ts`

**Step 1**: `nginx.conf` 加 `location /healthz { proxy_pass http://chatbiz-mcp:8004; }`
**Step 2**: `health.ts` 默认 fetch 改 `/healthz`；保留 `VITE_ADMIN_HEALTH_DIRECT=1` fallback
**Step 3**: 验证：`curl http://localhost:5173/healthz` 200 + `grep "localhost:8004" health.ts` 仅在 fallback 分支命中

### Task 1.4: Makefile 入口

**Files:**
- Create: `Makefile`

**Step 1**: 写 4 子命令（`up` / `down` / `test` / `logs`）
**Step 2**: `up` 前置 `docker compose -p chatbiz down` 检查
**Step 3**: `test` 串行调 3 套测试（canvas vitest integration + canvas playwright integration + admin playwright integration）
**Step 4**: 验证：`make test-integration up` 退出码 0 + 7 service 全 healthy

## Phase 2: API 集成测试（canvas + admin 后端契约）

### Task 2.1: canvas vitest integration 配置

**Files:**
- Create: `web/canvas/vitest.integration.config.ts`
- Create: `web/canvas/tests/integration/global-setup.ts`
- Modify: `web/canvas/package.json`（加 `test:integration` script）

**Step 1**: 写 `vitest.integration.config.ts`（environment: 'node' + include `tests/integration/**` + timeout 30s + globalSetup）
**Step 2**: 写 `global-setup.ts` 轮询 `localhost:5173/healthz` 60s
**Step 3**: `package.json` 加 `"test:integration": "vitest run --config vitest.integration.config.ts"`
**Step 4**: 验证：`pnpm test:integration` 启动 + 故意改错端口 60s 内 fail

### Task 2.2 ★: canvas api-client.spec.ts（6 case 真打后端）

**Files:**
- Create: `web/canvas/tests/integration/api-client.spec.ts`

**Step 1**: 写 6 case（登录 / 列表 / 创建 / 启动 run / 查结果 / 401）
**Step 2**: 加 3 边界 case（5xx runtime / 400 user / timeout network）
**Step 3**: 写 test helper（createTenant / truncateTenant / withAuth）
**Step 4**: 验证：`pnpm test:integration` 全部 pass + apiClient.ts 覆盖率 100%

## Phase 3: E2E（canvas paul 月报 + admin health）

### Task 3.1: canvas playwright integration 配置

**Files:**
- Create: `web/canvas/playwright.integration.config.ts`
- Modify: `web/canvas/package.json`（加 `e2e:integration` script）

**Step 1**: 写 `playwright.integration.config.ts`（baseURL 5173 + project integration + fullyParallel: true + retries: 1）
**Step 2**: `package.json` 加 `"e2e:integration": "playwright test --config playwright.integration.config.ts"`
**Step 3**: 验证：`npx playwright test --config playwright.integration.config.ts --list` 列出 ≥5 spec

### Task 3.2 ★: paul-monthly-report.spec.ts（4 critical path ① 100%）

**Files:**
- Create: `web/canvas/e2e/integration/paul-monthly-report.spec.ts`

**Step 1**: 写 5 case（登录 → 建 workflow → 拖 LLM 节点配 `model = "echo-test"` → 启动 run → 看结果 + audit log 落地）
**Step 2**: 加 spec 注释 `// critical-path-1: paul-monthly-report` 给 verify 阶段 grep
**Step 3**: 写 test helper（apiLogin / dragNode / waitForRunComplete）
**Step 4**: 验证：`npx playwright test --config playwright.integration.config.ts e2e/integration/paul-monthly-report.spec.ts` 全 pass

### Task 3.3: admin playwright integration 配置 + admin-health.spec.ts

**Files:**
- Create: `web/admin/playwright.integration.config.ts`
- Create: `web/admin/e2e/integration/admin-health.spec.ts`
- Modify: `web/admin/package.json`（加 `e2e:integration` script）

**Step 1**: 写 `playwright.integration.config.ts`（fullyParallel: false —— admin health 是全局单探针）
**Step 2**: 写 3 case（绿点 / 停 mcp 看红点 / 启回看恢复）+ access log 断言（`docker compose -p chatbiz-test logs mcp`）
**Step 3**: `package.json` 加 script
**Step 4**: 验证：`npx playwright test --config playwright.integration.config.ts e2e/integration/admin-health.spec.ts` 全 pass + access log 含 `GET /healthz`

## Phase 4: 文档 + 端到端验收

### Task 4.1: README + 排错文档

**Files:**
- Create: `web/integration-tests/README.md`

**Step 1**: 写开发命令（`make test-integration up/down/test/logs`）
**Step 2**: 写排错章节（5173 端口被占 / mcp 不可达 / 4 critical path 覆盖状态 / CI 接入指引）
**Step 3**: 验证：手读通顺 + 不暴露 test 凭据

### Task 4.2 ★: 端到端跑通

**Step 1**: 干净 dev 机（停 production compose + 停所有 docker 容器）
**Step 2**: `make test-integration up` 起 test 栈（cold start ≤5min）
**Step 3**: `make test-integration test` 跑 3 套测试（≤30min）
**Step 4**: 收集 Junit XML 报告到 `test-results/junit-*.xml`
**Step 5**: grep `// critical-path-1: paul-monthly-report` 验 4 critical path ① 覆盖

---

## Critical Path

**Phase 1 → Phase 2 → Phase 3 → Phase 4 串行**（每 phase 内部可部分并行）：
- Phase 1: 1.1 → 1.2/1.3 → 1.4（1.2 + 1.3 并行；1.4 收尾）
- Phase 2: 2.1 → 2.2（2.1 配置是 2.2 spec 的前置）
- Phase 3: 3.1 → 3.2/3.3（3.2 canvas + 3.3 admin 可并行）
- Phase 4: 4.1 → 4.2（4.1 文档与 4.2 端到端可并行，但 4.2 是 release gate）

★ 标注 = 高风险 task（应用 superpowers:test-driven-development 先写 test 再写 impl）

## 关键依赖

- 后端 4 service 的代码（既已由 `credential-management` / `workflow-engine` / `mcp-fetch-server` / `mcp-filesystem-server` / `mcp-postgres-server` / `audit-and-isolation` 等 change 锁定）**必须先于**本 change 落地 —— 至少 1 个真实 service + 1 个真实 LLM 端点（echo stub 算）必须可调通
- `web/` 前端基础（admin-bootstrap 落地）+ canvas 既有 e2e 框架必须先就位
- `infrastructure/docker-compose.yml` 既有 production compose 是 test compose 的镜像 source of truth（image tag 复用）

## 风险节点

1. **Task 1.2** echo stub 与 audit-and-isolation 路由表整合 —— 需先看 `services/audit-and-isolation/app/main.py` 现有 LLM 路由结构（apply 阶段再 deep dive）
2. **Task 2.2** apiClient.ts 现有代码 + 错误边界类（eng-review Quality #3）—— apply 阶段先 Read 既有源码再写
3. **Task 3.2** canvas 编辑器 + node 拖拽交互 —— apply 阶段 Read 既有 `e2e/paul-monthly-report.spec.ts`（mock 版）参照其 selector
4. **Task 4.2** cold start 时间 —— dev 机性能差异大；如超时则按 spec §"Test #1" 退到分阶段跑（vitest integration 先 → playwright 后）

## 验收 gate（apply 完成后 → verify 阶段）

- [ ] 所有 task 在 tasks.md 已 `- [x]`
- [ ] `make test-integration test` 一次跑通（vitest + 2 套 playwright）
- [ ] 4 critical path ① 100%（grep `// critical-path-1: paul-monthly-report` 注释）
- [ ] 4 critical path ②③④ 留 spec 钩子（grep `// critical-path-N: <name>` 在 web-e2e-orchestration spec 注释）
- [ ] production 路径不暴露 echo stub（verify check 1.4）
- [ ] nginx `/healthz` proxy 工作（verify check 4.3）
- [ ] admin health 容器化后仍工作（verify check 7.4）
- [ ] Junit XML 报告全 pass
