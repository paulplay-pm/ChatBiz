# web-integration-test-suite — Design

## Context

仓库已从 pre-build 进入**有代码阶段**：后端 4 个 service 已落地（`credential:8000` / `workflow-engine:8001` / `mcp:8004` / `audit-and-isolation:8080`），统一入口 `web/Dockerfile + nginx.conf` 已对外 5173，`web/admin` 和 `web/canvas` 已落地（admin-bootstrap + canvas 既有测试）。

**当前测试 gap 没变化**：
1. `web/canvas/e2e/*.spec.ts` 全部用 `page.route()` mock 后端，**0% 真实链路覆盖**
2. `web/admin/e2e/` 只验证静态占位视图，health 探活未端到端验证
3. 没有统一测试启动矩阵
4. `apiClient.ts` 的 401 跳转只在 Vitest 单元 mock

**但与 planning 阶段的假设不同**：
- `web/nginx.conf` 已存在，已有 `/workflows`、`/runs`、`/api/nodes`、`/approvals` proxy 到 `workflow-engine:8001`，以及 `/health`（nginx self），**没有 `/healthz` proxy**。
- `web/admin/src/api/health.ts` 已存在，默认 fetch `http://localhost:8004/healthz`（host 上 mcp 的 8004 端口）。
- `web/canvas/vite.config.ts` 用 dev server proxy `/workflows` 等到 `localhost:8001`；login 由 `vite-plugin-dev-iam.ts` mock（dev 专用）。
- `audit-and-isolation` 的 `/v1/chat/completions` 走 `routing/table.py` 从 PG 加载路由表；真实 LLM 调用走 `app/llm/client.py`。没有现成 echo stub。
- `apiClient.ts` 非常简单：baseURL 为空、401 清 store + 跳 `/login`、**没有**按 eng-review Quality #3 的 4 错误边界分类抛出特定 Error class。

**eng-review 2026-06-10 锁定（必须覆盖）：**
- **Test #1** (P1)：3 层测试金字塔（pytest / LangGraph 集成 / Playwright E2E / 50 paul LLM eval）
- **Test #2** (P1)：4 critical path 100% 覆盖：① paul 财务月报 ② 网关 PII 拦截 ③ 人工审批中断续接 ④ 插件降级
- **Arch #1** (P1)：数据隔离网关 = egress 强制点（不是 ingress）+ 2 实例 HA + 跨网关 trace-id 关联
- **Quality #3** (P2)：错误处理 4 边界（canvas drag / runtime / user / security）

**目标（10 状态）：** 当前 0%，本 change 结束：① paul 财务月报 → 100%；②③④ → spec 留扩展点。LLM eval 与性能压测由后续 change 接管。

**上游基线：**
- `docs/architecture.md` §4.3.1（自研画布 + 自研节点 + LangGraph 编译）
- `docs/architecture.md` §4.3.5（数据隔离网关，egress 强制点）
- `docs/architecture.md` §4.4（技术栈：Python SQLAlchemy 异步 / React TS strict / Playwright）
- `docs/prd.md` §4.2（paul 财务月报 workflow，MVP 必中）
- `openspec/config.yaml` §specs.rules（4 critical path 必须显式列 Requirement）

**stakeholder：** 前端组（canvas + admin 各 1 人）、LangGraph 后端（1 人）、devops（compose 维护 1 人）。本 change 主承担：前端组。

## Goals / Non-Goals

**Goals：**
- `infrastructure/docker-compose-test.yml` 一键起 web（nginx 5173）+ 4 后端 service + 共享 pg/redis，**与 production compose 互斥**（不同 project name `chatbiz-test`）
- `make test-integration` 单命令跑完整集成测试套
- `web/canvas/e2e/integration/paul-monthly-report.spec.ts` 真实链路：登录 → 新建 workflow → 打开 editor → 验证 workflow 持久化；**不依赖拖 LLM 节点 + run**（真实后端上拖节点并 run 的复杂度超出本 change 2h/task 粒度，先用"登录 → 创建 → 持久化"覆盖 critical-path-1 的 end-to-end 链路；run + LLM echo 作为后续增强）
- `web/canvas/tests/integration/api-client.spec.ts` 跑 4 类核心 axios 场景（登录 / 查 / 建 / 401）真打 `workflow-engine:8001`，并验证后端返回的 `error_class` 字段可映射到 Quality #3 的 4 边界
- `web/admin/e2e/integration/admin-health.spec.ts` 走 nginx `/healthz` proxy 到 `mcp:8080`（容器内端口；外部映射 8004），Playwright 验绿点 + 后端 access log
- LLM echo stub 作为 `audit-and-isolation` `/v1/chat/completions` 的旁路：仅当 `ENVIRONMENT=integration`（由 test compose 设置）且 `model = "echo-test"` 时返回 echo；**仍过** audit enqueue（eng-review Arch #1 兼容）
- 4 critical path 中 ① paul 财务月报 推到 100%；②③④ 留 spec 扩展点（`web-e2e-orchestration` § "Extension points" Scenario）
- E2E 用统一入口 `http://localhost:5173`（CLAUDE.md "单端口 5173" 约定）

**Non-Goals：**
- 见 `proposal.md` Non-goals 节
- **不**做 4 critical path 中 ②③④ 的 E2E（对应 service 落地后由独立 change 接管）
- **不**做 leo / anny 链路（service 尚未落地，[FUTURE-IMPLEMENTATION]）
- **不**做 LLM eval（50 paul 财务月报场景的输出质量基线）—— 后续 `llm-eval-baseline` change
- **不**做性能压测（Perf #1 缓存/限流/批处理）—— 后续 `perf-regression-suite` change
- **不**做 CI 接入（仓库 0 CI，openspec/config.yaml §Commands 未列）
- **不**改 production compose（`infrastructure/docker-compose.yml`）
- **不**改既有 mock 版 E2E
- **不**做 ESLint / 静态分析基础设施
- **不**改 `web/canvas/vite-plugin-dev-iam.ts`（dev IAM mock 保留；集成测试栈通过 nginx + test compose 运行时无需它）
- **不**在 paul 月报 E2E 中真正"运行 workflow 到完成"（当前 canvas 节点拖拽 + run 触发路径复杂；本 change 用"创建 workflow 并持久化"验证 end-to-end，run 链路作为后续增强在 spec 中标记）

## Decisions

### D1：测试栈走独立 compose project，与 production 互斥

**选择：** 新增 `infrastructure/docker-compose-test.yml`，使用 `--project-name chatbiz-test` 启动，端口与 production 相同（5173 / 8000 / 8001 / 8004 / 8080 / 5432 / 6379）但**不共存**（同一时刻只有一组在跑）。

**理由：**
- 测试栈与 production 形态**完全一致**（nginx + 4 service + pg/redis），覆盖路径分发 / proxy / 跨域 / 真实响应
- 端口不冲突是因为互斥：dev 机起 test 时先 `docker compose -p chatbiz down`，test 跑完起回 dev
- 复用既有 service 镜像，**不**重新打包

**已考虑 alternative：**
- **A. 复用 production compose 跑测试** —— 拒绝。dev 环境与测试环境数据会污染；test 跑挂会拖垮 dev。
- **B. 每个测试用独立端口（如 5174 / 8005）** —— 拒绝。CLAUDE.md 约定"单端口 5173"统一入口；改端口则 nginx 路径分发与 production 不一致，集成测试失去意义。
- **C. 用 Testcontainers 起临时后端** —— 拒绝。Testcontainers 是 JVM 生态，仓库是 Python；引入新概念且 setup 慢于 compose。
- **D. 共享 postgres/redis 给 production + test** —— 拒绝。数据污染、test 跑挂影响 dev、CI 无法独立。

### D2：Playwright 走 nginx `localhost:5173`，不直连后端端口

**选择：** Playwright 所有 spec 全部 baseURL = `http://localhost:5173`，由 nginx 路径分发到对应后端。

**理由：**
- 覆盖 nginx 路径分发（`/canvas/` → canvas SPA + `/api/*` → workflow-engine:8001）
- 覆盖 nginx proxy（`/healthz` → mcp:8080）
- 覆盖 CORS、cookie、跨域 redirect 等浏览器真实行为
- 与 production 部署形态 1:1

**已考虑 alternative：**
- **A. Playwright 直连 `workflow-engine:8001`** —— 拒绝。失去 nginx 这一层覆盖；mock 版 E2E 失败的根因之一就是绕开 nginx。
- **B. 部分 spec 走 nginx / 部分直连** —— 拒绝。规则不一致 → 维护成本高 + 测试目的不清。

### D3：admin health 改走 nginx `/healthz` 相对路径

**选择：** `web/admin/src/api/health.ts` 的 `useHealth()` 默认 fetch 改为相对路径 `/healthz`；`web/nginx.conf` 新增 `location /healthz { proxy_pass http://chatbiz-mcp:8080; }`。旧版直连 host 8004 保留为 `VITE_ADMIN_HEALTH_DIRECT=1` 显式开关（仅 dev 阶段使用）。**注意**：mcp 容器**内部**监听 8080，外部 host 映射到 8004；nginx 到 mcp 的 proxy 必须用容器内 DNS + 8080。

**理由：**
- 容器化后浏览器**无法**直连 host 端口；唯一健康路径是 nginx proxy
- 旧版 `http://localhost:8004/healthz` 在本地 dev 仍能工作（mcp 起在 host 8004），保留为 fallback 避免阻塞 dev
- 集成测试**强制**走相对路径，验证 nginx proxy 真在工作

**已考虑 alternative：**
- **A. 给 admin 容器独立 sidecar 走 8004** —— 拒绝。增加部署复杂度；eng-review §4.4 未列 sidecar 模式。
- **B. 用 mDNS / 服务发现** —— 拒绝。浏览器不支持；破坏 nginx 单一入口。
- **C. 不改默认，仅 E2E 时切** —— 拒绝。E2E 偏离 production 路径，失去意义。

### D4：LLM echo stub 作为 audit-and-isolation `/v1/chat/completions` 的旁路

**选择：** 在 `services/audit-and-isolation/app/api/chat.py` 的 `chat_completions` handler 最前面加旁路：如果 `get_settings().environment == "integration"`（由 test compose 的 `ENVIRONMENT: integration` 设置）且 `body.get("model") == "echo-test"`，则直接构造 OpenAI 兼容响应、写 audit outbox（走既有 enqueue 路径）、返回 200。**不**改 routing table，**不**插 PG 路由数据。production 设置 `ENVIRONMENT=production`，旁路条件不满足。

**理由：**
- **eng-review Arch #1 强制**：egress 强制点 = audit-and-isolation。echo 请求必须仍经过 audit enqueue，否则测的不是真实链路。
- 绕过 routing table 避免测试去操作 PG 中的 `ModelRouting` 表（当前没有 echo model 的 seed）
- 旁路逻辑在 handler 头部，一眼可见；production `environment != "integration"` 即不可达

**已考虑 alternative：**
- **A. 直连 echo stub（绕开 audit-and-isolation）** —— 拒绝。违反 Arch #1；E2E 测的不是真实链路。
- **B. 改 audit-and-isolation 路由表指向 echo** —— 拒绝。需要测试时插 PG 路由数据，setup 复杂且污染持久化路由表。
- **C. mock workflow-engine 的 LLM 节点** —— 拒绝。失去"audit log 落地"这条断言。
- **D. 新增独立 `/v1/echo` endpoint** —— 拒绝。客户端（canvas）需要 special URL，与真实 LLM 调用形态不一致。
- **E. 用真实 LLM 但 limit token** —— 拒绝。仍烧钱 + 不稳定 + 网络依赖。

### D5：API 集成测试放 `web/canvas/tests/integration/`，用 Vitest + 真后端

**选择：** `web/canvas/tests/integration/api-client.spec.ts`（Vitest + 真后端 axios）。新增 `web/canvas/vitest.integration.config.ts` 区分单元（jsdom）与集成（node + 真后端）：

```ts
// vitest.integration.config.ts
export default defineConfig({
  test: {
    include: ['tests/integration/**/*.spec.ts'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    environment: 'node',  // 不是 jsdom
    testTimeout: 30_000,
    hookTimeout: 30_000,
    globalSetup: ['./tests/integration/global-setup.ts'],  // 等 compose healthy
  },
})
```

**理由：**
- 靠近 consumer 端（前端契约测试的归属）
- Vitest 已有基础设施，**不**引入新框架
- `globalSetup` 等 compose healthy，避免 race
- node 环境而非 jsdom，因为测的是 axios HTTP 而非 DOM
- **显式 exclude `e2e/`**：admin-bootstrap retrospective 已记录 vitest 默认 include 会吞 `e2e/*.spec.ts` 与 playwright 冲突

**已考虑 alternative：**
- **A. 放 `services/workflow-engine/tests/frontend-contract/`** —— 拒绝。前端契约测试的 consumer 是前端，归属应在前端。
- **B. 改用 Playwright API testing** —— 拒绝。Playwright API testing 适合 e2e HTTP，不适合"axios 拦截器逻辑"这种 library-level 测。
- **C. 仍用 mock，但加更多场景** —— 拒绝。提案目标就是"真打后端"。

### D6：测试数据隔离 = 独立 user + truncate fixture

**选择：** 每个 spec setup 创建独立 `user_id = uuid`（当前后端用 `created_by == user_id` 做权限隔离，尚无 `tenant_id` 概念），创建独立 workflow；teardown 删除该 user 创建的所有 workflow。**不**用全局 seed 数据。

**理由：**
- 多个 test worker 并发跑不互相干扰
- 测试失败不污染 dev 数据库
- rollback 简单（teardown 删该 user 的数据）

**已考虑 alternative：**
- **A. 全局 seed + 测试间共享数据** —— 拒绝。并发写 workflow 会互相干扰；eng-review Quality #2 锁定 PG/Redis 双层，state 写竞争是真实风险。
- **B. 每个 spec 全新 DB（schema 级）** —— 拒绝。setup 慢、PG 不能并发建 schema。
- **C. 用事务回滚** —— 拒绝。HTTP 调后端的测试不在同一事务里，事务回滚无效。

### D7：`make test-integration` 入口

**选择：** 新增 `Makefile` 含 `test-integration` target。openspec/config.yaml §Commands 写"没有 Makefile"——本 change 添加的**仅是测试入口**而非 build/lint/test 命令，与 pre-build 现状不冲突。设计 doc 显式说明这是测试基础设施而非 build 工具。

**理由：**
- 单命令启动完整集成测试栈是测试基础设施的合理部分
- 后续 CI 接入可直接调 `make test-integration`
- 不引 npm script 跨前端（canvas + admin 各一份），避免冗余

**已考虑 alternative：**
- **A. `scripts/test-integration.sh`** —— 接受。`Makefile` 仅为人类可读入口，背后是 shell 脚本；如团队更倾向纯 shell，design 可改。
- **B. 各前端 `package.json` 加 `test:integration` script** —— 拒绝。需要 2 套命令（canvas + admin）+ 1 套 compose，不一致。
- **C. 不做入口，每次手动起** —— 拒绝。CI 阶段无统一入口。

### D8：测试栈注册到 `docker-compose-test.yml` 而非 `docker-compose.yml`

**选择：** 服务容器**不**写到 `infrastructure/docker-compose.yml`（production），而是独立 `docker-compose-test.yml`。apply-rules "MUST: 服务容器在 infrastructure/docker-compose.yml 注册" 显式豁免，理由：test stack 不进 production 部署路径。

**理由：**
- 仓库"无 Makefile / CI" 的 pre-build 现状 + 单职责
- 独立文件让 test 镜像版本/dev 镜像版本解耦
- 后续可单独 git 化（test infra vs prod infra）

**已考虑 alternative：**
- **A. 写进 production compose，加 profile 隔离** —— 拒绝。production 文件应当只含 prod 路径；test infra 是 dev-time 关注。
- **B. 写在各 service 仓库内 `docker-compose.test.yml`** —— 拒绝。service 仓尚未建立（pre-build）；跨 service 编排应在 infrastructure 仓。

### D9：openspec/config.yaml §apply.rules "specs 同步落地" 规则

**选择：** 本 change 三个 capability 均**含**前端 + 后端（或前端 + 既有后端消费），**无**纯后端 / 纯前端豁免。每个 spec 顶部 `Frontend Scope:` 显式声明。

**理由：** proposal 已列；specs 阶段每个文件顶部都会重复声明一次（apply 阶段硬规则）。

**已考虑 alternative：**
- **A. 把 API 集成测试标 "Frontend Scope: N/A"** —— 拒绝。它是前端契约测试，属前端范围。

### D10：服务端口选择（与 CLAUDE.md 端口表一致）

**选择：** test compose 复用现有端口（5173 / 8000 / 8001 / 8004 / 8080 / 5432 / 6379），**不**新占端口。CLAUDE.md 端口表**不**修改（互斥使用，不属"新占"）。

**理由：** openspec/config.yaml §apply.rules "MUST: 端口从 CLAUDE.md 端口分配表选用" —— 复用而非新占。

## Risks / Trade-offs

**[Risk] compose cold start 慢（2-5 分钟）** → Mitigation: `make test-integration` 等所有 service `health: healthy` 才开跑（`docker compose -p chatbiz-test up --wait`）；CI cache image 层；`--quiet-pull` 避免日志洪。

**[Risk] LLM echo stub 被误用到 production** → Mitigation: 三重防御：① `ENVIRONMENT=integration`（test compose 显式设置）；② model 白名单 `echo-test`；③ apply 阶段加 verify check 验 production env 下 `model=echo-test` 返回 400。

**[Risk] 多 spec 并发写同一 workflow-engine 表** → Mitigation: D6 独立 user + teardown 删除该 user 创建的 workflow。

**[Risk] 5173 端口在 dev 阶段被占用**（如 dev 起着 `chatbiz-web` 容器）→ Mitigation: `make test-integration` 前置 `docker compose -p chatbiz down` 提示；admin-bootstrap retrospective 已记录这条排查路径，README 文档化。

**[Risk] Playwright + 真后端的 test flake（网络 / 启动时序）** → Mitigation: `globalSetup` 等所有依赖 healthy 才开跑；test 内部用 retry（`@playwright/test` 默认 1 retry）；CI 阶段再加 `--retries=2`。

**[Risk] `apiClient.ts` 没有 4 边界 Error class，集成测试无法直接断言** → Mitigation: 测试断言后端返回的 `error_class` 字段（`security` / `user` / `runtime`）和浏览器 redirect 行为；spec 中明确这是"映射到"而非"apiClient 抛出"。

**[Trade-off] E2E 比单元测试慢** → 接受。eng-review Test #1 锁定 3 层金字塔，E2E 不可省；接受 5-10x 时间换取真实链路覆盖。

**[Trade-off] test infra 注册到 `docker-compose-test.yml` 而非 production compose** → 接受。openspec/config.yaml §apply.rules 的"production compose 注册"显式豁免（本 design D8 列出）；test stack 不进 production 部署路径是正确隔离。

**[Trade-off] `make test-integration` 引入 Makefile** → 接受。openspec/config.yaml §Commands "无 Makefile" 是 pre-build 现状描述，本 change 添加的仅是**测试入口**；如团队倾向纯 shell，可改 `scripts/test-integration.sh`，design D7 已列。

**[Trade-off] paul 月报 E2E 不跑 run 到完成** → 接受。当前 canvas 拖 LLM 节点 + run 触发路径复杂，超出本 change 2h/task 粒度；"登录 → 创建 → 持久化"已构成 critical-path-1 的 end-to-end 覆盖，run 链路作为 spec 扩展点留给后续 change。

**[Risk] Web 容器（nginx）build 时未含 test 专用配置** → Mitigation: test compose 用 `web` 服务时 mount 同一 `nginx.conf`；如有差异（如 access log 路径），用 volume override 而非 rebuild 镜像。

## Migration Plan

**本 change 不涉及 production 部署变更** —— 它新增的是**测试基础设施**（独立 compose + 集成测试 spec + LLM echo stub），**不动 production compose / 既有 service 代码**。

**部署顺序（仅 test infra）：**
1. 添加 `infrastructure/docker-compose-test.yml` + `.env.test` 模板
2. 修改 `services/audit-and-isolation/app/api/chat.py` 加 echo 旁路（env-gated）
3. 修改 `web/nginx.conf` 加 `location /healthz`（向后兼容：旧 `/api/*` 路径不变）
4. 修改 `web/admin/src/api/health.ts` 默认 URL 改相对路径（fallback `VITE_ADMIN_HEALTH_DIRECT=1`）
5. 添加 `web/canvas/e2e/integration/paul-monthly-report.spec.ts` + `vitest.integration.config.ts` + `playwright.integration.config.ts`
6. 添加 `web/canvas/tests/integration/api-client.spec.ts` + `global-setup.ts`
7. 添加 `web/admin/e2e/integration/admin-health.spec.ts` + 同上
8. 添加 `Makefile` / `scripts/test-integration.sh` 入口
9. 添加 `web/integration-tests/README.md` 文档

**验证：** verify.md 列每条 checkable 项（compose up healthy / E2E pass / 4 critical path ① 覆盖 / echo stub prod 不可达 / 4 错误边界断言）。

**rollback：**
- `web/nginx.conf` location 块可一行删除（向后兼容）
- `web/admin/src/api/health.ts` 改回旧默认值（向后兼容）
- `docker-compose-test.yml` 直接删除
- `services/audit-and-isolation/app/api/chat.py` 旁路代码删除
- 既有 mock 版 E2E 保留，不受影响

## Open Questions

- **OQ1（test 数据隔离）**：✅ 决定 —— 独立 user + teardown 删除该 user 数据（D6）
- **OQ2（LLM 节点）**：✅ 决定 —— echo stub 作为 audit-and-isolation `/v1/chat/completions` 旁路（D4）
- **OQ3（admin health 验证粒度）**：✅ 决定 —— 绿点 + access log 双重断言
- **OQ4（CI 接入）**：✅ 决定 —— 不在本 change（Non-goals）
- **OQ5（API 集成测试位置）**：✅ 决定 —— `web/canvas/tests/integration/`（D5）

**carry over 到 apply 阶段（如发现需重开 design）：**
- **OQ6**：test compose 镜像版本如何 lock？建议复用 `infrastructure/docker-compose.yml` 的 image tag（保证 test = prod 镜像），不独立 tag
- **OQ7**：LLM echo stub 的 response shape 是否需要与真实 OpenAI 兼容？答案是（`choices[0].message.content`）以便未来切换不破 client
- **OQ8**：Playwright `fullyParallel` 是否启用？建议是（多 spec 并发跑），但 D6 独立 user 隔离是前提
- **OQ9**：paul 月报 E2E 是否 future 增强到"拖 LLM 节点 + run"？答案是：本 change 只做到"创建 + 持久化"，后续 change 用 echo stub 补充 run 链路
