# web-integration-test-suite — Proposal

## Why

仓库 `web/` 下两个前端（`web/canvas` 编辑器 + `web/admin` 管理后台）已落地，但**集成测试全靠 mock**：`canvas/e2e/*.spec.ts` 全部用 `page.route()` 拦截后端响应，`admin/e2e/` 只验证静态占位视图。后端 `services/{credential,workflow-engine,mcp,audit-and-isolation}` 已分配端口、声明 schema，但端到端链路（"登录 → 建 workflow → 运行 → 看结果"）从未在真实 stack 上跑过。

eng-review 2026-06-10 **Test #1**（P1）已锁定 "3 层测试金字塔 + LLM eval（pytest / LangGraph 集成 / Playwright E2E / 50 paul 场景 LLM eval）"、**Test #2**（P1）已锁定 "4 critical path 100% 覆盖：paul 财务月报 / 网关 PII 拦截 / 人工审批中断续接 / 插件降级"。**当前 0%** 覆盖：playwright 全 mock，LLM eval 不存在，4 critical path 一条都没碰。

不改：MVP 阶段（month 2-3）paul 财务月报 workflow 一旦上线，回归靠人肉点鼠标，发现 bug 靠 Slack 截图 — 锁不进 eng-review 的 P1 acceptance。  
改：建一套 **web 集成测试基础设施**（统一 compose 启动矩阵 + Playwright 走 nginx 5173 + axios 真实后端 + LLM echo stub），让 paul 月报 E2E 真正打到 `workflow-engine:8001` 与 `audit-and-isolation:8080`，**仅这一条**就把 Test #2 的 4 critical path 中 ① paul 财务月报 推到 100%，并为 ② 网关 PII 拦截、③ 人工审批中断续接、④ 插件降级 留好扩展点。

参考基线：
- `docs/architecture.md` §4.3.1 自研画布 + 自研节点 + LangGraph 编译
- `docs/architecture.md` §4.3.5 数据隔离网关（egress 强制点）
- `docs/prd.md` §4.2 paul 财务月报 workflow（MVP 必中场景）
- `docs/architecture.md` §4.4 技术栈（Python SQLAlchemy / React TS strict / Playwright）
- eng-review 决策 Test #1、Test #2、Arch #1（egress 强制点）、Quality #3（4 错误边界）

## What Changes

**统一测试启动矩阵**
- **From**：当前 Playwright 测试全靠 `page.route()` mock 后端，admin E2E 只验证占位视图，测试跑通 ≠ 集成工作。
- **To**：新增 `infrastructure/docker-compose-test.yml` 一键起 `web`（nginx 5173） + 后端 4 个 service（credential:8000 / workflow-engine:8001 / mcp:8004 / audit-and-isolation:8080） + 共享 postgres:5432 + 共享 redis:6379，Playwright 走 `http://localhost:5173/canvas/` + `/admin/` 真实链路。
- **Reason**：CLAUDE.md 已约定"单端口 5173"统一入口；走 nginx 而非直连后端端口，能同时覆盖路径分发 + proxy + 跨域 + 真实响应，mock 永远发现不了这些。
- **Impact**：non-breaking。新增 compose 文件，**不**改 production compose（`docker-compose.yml`）；CI（未来）按需引用。

**API client 集成测试（替代/补充 mock）**
- **From**：`web/canvas/src/lib/apiClient.ts` 的 axios 拦截器（401 跳转、错误分类）只在 Vitest 单元测试里 mock，**从未真正打过后端**。
- **To**：新增 `web/canvas/tests/integration/api-client.spec.ts` —— 在 compose 起来的栈上跑 `apiClient` 的 6 类核心场景：登录 POST /api/auth/login、查询 GET /api/workflows、创建 POST /api/workflows、运行 POST /api/runs、401 跳转、5xx 错误边界分类。
- **Reason**：错误边界（eng-review Quality #3）只有真打后端才能验：5xx 是否走 `WorkflowRuntimeError`、401 是否触发 `security` 边界、参数不全是否走 `user` 边界。
- **Impact**：non-breaking。新增测试目录，不动 `apiClient.ts` 源码。

**paul 财务月报 E2E 真实链路**
- **From**：`web/canvas/e2e/paul-monthly-report.spec.ts` 存在但全程 `page.route()` mock；不验证 proxy、不验证 nginx、不验证 audit-and-isolation 链路。
- **To**：新增 `web/canvas/e2e/integration/paul-monthly-report.spec.ts` —— 走真实 compose 栈：登录 → 新建 workflow → 拖入 LLM 节点（**echo stub 替换真实 LLM**，避免烧钱）→ 运行 → 在 `/canvas/runs/:runId` 看到结果 + 看到 audit log 在 audit-and-isolation 落地。
- **Reason**：Test #2 4 critical path 之一，**本 change 是它的 100% 覆盖 deliverable**。
- **Impact**：non-breaking。新增 spec 文件，旧 mock 版 spec 保留（pure UI 反馈用途）。

**admin health 探活 E2E**
- **From**：`web/admin/src/api/health.ts` 的 `useHealth()` 默认 fetch `http://localhost:8004/healthz`，**绕开 nginx**；在 docker 内浏览器无法直连 host 8004。
- **To**：把 health 调用统一为相对路径 `/healthz`（走 nginx proxy）；`web/nginx.conf` 新增 `location /healthz { proxy_pass http://chatbiz-mcp:8004; }`；新增 `web/admin/e2e/integration/admin-health.spec.ts` —— 打开 `/admin` → header bar 看到绿点 → 后端 mcp service 真的收到 `/healthz` 请求（用 access log 验证）。
- **Reason**：admin Web 容器化后，**唯一健康**的 mcp 调用路径就是 nginx proxy；让 E2E 锁住这条路径。
- **Impact**：non-breaking。修改 `useHealth()` 默认 URL + nginx.conf 一行；旧版直连 host 的 fallback 在 dev 阶段保留（`VITE_ADMIN_HEALTH_DIRECT=1`）。

**LLM echo stub**
- **From**：真实 LLM 调用贵、慢、不稳定；不允许测试 burn token。
- **To**：新增 `services/audit-and-isolation/app/llm_echo_stub.py` —— 一个 deterministic echo 后端，接收 `{"model": "...", "messages": [...]}` 返回 `{"choices": [{"message": {"content": "ECHO: <msg>"}}]}`，**仅**在 `INTEGRATION_TEST=1` 环境变量下注册到 `audit-and-isolation` 的 LLM 路由表。production 环境变量不设则不可达。
- **Reason**：eng-review Arch #1 锁定"egress 强制点 = audit-and-isolation"，LLM stub **必须**挂在 audit-and-isolation 之后，**不能**绕开，否则 E2E 测的不是真实链路。
- **Impact**：non-breaking。production 路径不暴露 echo stub。

## Capabilities

### New Capabilities

- `web-e2e-orchestration`：**测试基础设施 capability**。含 compose 启动矩阵、nginx healthz proxy、LLM echo stub、Playwright 复用 baseURL。**前端范围** = `web/canvas/e2e/integration/` + `web/admin/e2e/integration/` + `web/nginx.conf` 增量 + `web/Dockerfile` 集成测试 target。**后端范围** = `services/audit-and-isolation/app/llm_echo_stub.py` + `infrastructure/docker-compose-test.yml`。**豁免前端** = 不适用（含前端+后端）。

- `canvas-api-integration`：**API client 集成测试 capability**。含 6 类核心 axios 场景 + 错误边界分类断言。**前端范围** = `web/canvas/tests/integration/api-client.spec.ts`（Vitest + 真后端）。**后端范围** = 无新增（消费既有 `services/workflow-engine` API）。**豁免前端** = 不适用。

- `admin-health-integration`：**admin 健康探活 E2E capability**。含 `/healthz` 路径代理、useHealth 切相对路径、Playwright 验证绿点 + access log。**前端范围** = `web/admin/src/api/health.ts` 改默认 + `web/admin/e2e/integration/admin-health.spec.ts` + `web/nginx.conf` location。**后端范围** = `services/mcp:8004/healthz`（既有）。**豁免前端** = 不适用。

### Modified Capabilities

无。本 change 是 additive；不动既有任何 spec。

## Impact

- **代码层（新增）**：
  - `infrastructure/docker-compose-test.yml`（新）：测试栈
  - `web/nginx.conf`（改）：新增 `location /healthz`
  - `web/canvas/e2e/integration/paul-monthly-report.spec.ts`（新）：真实链路 E2E
  - `web/canvas/tests/integration/api-client.spec.ts`（新）：API 集成
  - `web/admin/e2e/integration/admin-health.spec.ts`（新）：health 探活 E2E
  - `web/admin/src/api/health.ts`（改）：默认 URL 改相对路径
  - `services/audit-and-isolation/app/llm_echo_stub.py`（新）：LLM echo
  - `web/canvas/playwright.config.ts`（可能改）：新增 integration project
  - `web/admin/playwright.config.ts`（可能改）：新增 integration project
  - `Makefile`（新）：`make test-integration` 入口（**新**基础设施命令，与 openspec/config.yaml "无 Makefile" 不冲突——这是测试命令而不是 build 命令；如团队介意可改为 `scripts/test-integration.sh`）
- **依赖（新增）**：
  - 前端：`@playwright/test` 已在两端用，无新依赖
  - 后端：`services/audit-and-isolation` 无新 pip 依赖（echo stub 用 stdlib）
  - 基础设施：复用既有 `postgres` / `redis` / `mcp` 镜像
- **CLAUDE.md 端口表**：不需新占端口。test compose 复用 5173 / 8000 / 8001 / 8004 / 8080 / 5432 / 6379，**与 production compose 互斥**（不同 compose project name）。
- **openspec/config.yaml 规则**：
  - `apply.rules` 触发"MUST: 服务容器在 infrastructure/docker-compose.yml 注册" —— **本 change 注册到 `docker-compose-test.yml`**，是独立测试栈而非 production 服务；在 design.md 显式说明豁免理由（test stack 不进 production 部署路径），并在 `apply-rules-check` 阶段 surface 出来。
  - `apply.rules` 触发"MUST: 引用 eng-review Arch #1 egress 强制点" —— **本 change 主动沿用**（echo stub 挂在 audit-and-isolation 之后），满足。
  - `specs.rules` 触发"4 critical path 必须显式列为 Requirement" —— 本 change 把 ① paul 财务月报 列为 web-e2e-orchestration 的 Requirement；②③④ 留 spec 钩子（"扩展点" Scenario），不在本 change 范围。
- **测试**：
  - 单元测试：沿用既有 `vitest run`，覆盖率不变
  - 集成测试：**新增** `vitest run --config vitest.integration.config.ts` + `playwright test --project=integration`
  - E2E：**新增** integration project
- **CI**：本 change **不**建 CI（仓库 0 CI；openspec/config.yaml §"Commands" 也未列）。CI 接入是后续 change。本 change 留 `Makefile` 入口便于 CI 阶段直接调。

## Non-goals

- **不**做 4 critical path 中 ② 网关 PII 拦截 / ③ 人工审批中断续接 / ④ 插件降级 的 E2E（这些需要 service 落地后由独立 change 接管；本 change 留 spec 扩展点）
- **不**做 leo（数据查询）/ anny（文档审核）的端到端链路（对应 service 尚未落地，[FUTURE-IMPLEMENTATION]）
- **不**做 LLM eval（50 paul 财务月报场景的输出质量基线）—— 由后续 `llm-eval-baseline` 独立 change 落地；本 change 只覆盖**链路**而非输出质量
- **不**做性能压测（Perf #1 缓存/限流/批处理）—— 由后续 `perf-regression-suite` 独立 change 落地
- **不**做 CI 接入 —— 仓库 0 CI 是 pre-build 现状决定；本 change 留 `make test-integration` 入口
- **不**改 production compose（`infrastructure/docker-compose.yml`）；test compose 独立
- **不**改既有 mock 版 E2E（pure UI 反馈价值仍在）
- **不**做 ESLint / 静态分析基础设施
- **不**做 401/403 的 RBAC 业务测试（credential 鉴权逻辑由 `credential-management` change 自测）

## Open Questions（延续 brainstorm OQ1-OQ5，design 阶段定稿）

- **OQ1**：E2E 测试数据隔离 —— design 阶段定：每个 spec 用独立 tenant + truncate fixture
- **OQ2**：LLM 节点用 echo stub（已选，见 What Changes）
- **OQ3**：admin health 探活验证到 access log 级别（已选，见 What Changes）
- **OQ4**：CI 不在本 change 范围（见 Non-goals）
- **OQ5**：API 集成测试放 `web/canvas/tests/integration/`（已选，原因：靠近 consumer 端，前端契约测试的归属）
