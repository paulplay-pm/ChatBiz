# web-integration-test-suite — Tasks

> **Scope**：建 web 集成测试基础设施（test compose + Playwright 真实链路 + API 集成测试 + admin health E2E + LLM echo stub）。完成后 eng-review **Test #2** 的 4 critical path 中 ① paul 财务月报 推到 100%；②③④ 留 spec 扩展点给后续 change 接管。
>
> **不**做：4 critical path ②③④ / leo anny 链路 / LLM eval / 性能压测 / CI 接入 / production compose 改动 / 既有 mock E2E 改动。
>
> **前置门**：仓库已有 4 个后端 service（credential / workflow-engine / mcp / audit-and-isolation）+ 2 个前端（web/canvas / web/admin）+ nginx 统一入口。本 change 在既有代码上**新增测试基础设施**，不动既有 service 业务代码。

## 0. 前置门

- [ ] 0.1 验 `docker --version >= 24` + `docker compose version >= 2.20` + `node --version >= 20` + `pnpm --version >= 8`。**编码规范**：engines 锁定。**安全清单**：使用官方 docker 镜像，不引可疑 source。验：`docker -v` + `docker compose version` + `node -v` + `pnpm -v`。

## 1. test compose 基础设施

- [ ] 1.1 新增 `infrastructure/docker-compose-test.yml`：7 service（web / credential / workflow-engine / mcp / audit-and-isolation / postgres / redis），端口与 production 一致（5173 / 8000 / 8001 / 8004 / 8080 / 5432 / 6379），`--project-name chatbiz-test` 与 production 互斥。`ENVIRONMENT=integration` 传给 audit-and-isolation 激活 echo stub。**编码规范**：格式与既有 `infrastructure/docker-compose.yml` 一致；mcp proxy 用容器内端口 `8080`。**安全清单**：所有 service 设 `read_only: false`（pg/redis 需写）+ postgres 设密码。验：`docker compose -p chatbiz-test config` 退出码 0 且无警告。
- [ ] 1.2 每个 service 加 `healthcheck`：`web` 用 `curl http://localhost/healthz`；`credential` / `workflow-engine` / `audit-and-isolation` 用 `curl http://localhost:<port>/healthz`；`mcp` 用 `curl http://localhost:8080/healthz`（**容器内端口 8080**）；`postgres` 用 `pg_isready`；`redis` 用 `redis-cli ping`。所有 `depends_on` 链 `service_composedly_successfully`。**编码规范**：openspec/config.yaml §apply.rules "MUST: 健康检查用 HTTP GET"。**安全清单**：healthcheck 不暴露敏感信息。验：`docker compose -p chatbiz-test up --wait` 等所有 healthy（最长 5min）。
- [ ] 1.3 新增 `infrastructure/.env.test` 模板（含 `ENVIRONMENT=integration` / `POSTGRES_PASSWORD=test_pw` / `LOG_LEVEL=info` 等）。**编码规范**：用 `${VAR:-default}` 语法。**安全清单**：test-only 凭据，**禁止** 与 production 同密码。验：`.env.test` 在 `.gitignore` 排除，`.env.test.example` 入库。
- [ ] 1.4 **验证**：1.1-1.3 跑通。`make test-integration up` 起 test 栈 + `docker compose -p chatbiz-test ps` 7 service 全 healthy。**任务配对验证**：与 1.1-1.3 编码任务一一对应。

## 2. Makefile + 单命令入口

- [ ] 2.1 新增 `Makefile` 含 `test-integration` target（4 子命令 `up` / `down` / `test` / `logs`）。**编码规范**：openspec/config.yaml §"Commands" 显式说"无 Makefile"——本 change 添加的**仅是测试入口**，不构成 build/lint/test 命令冲突；design.md D7 已记录。**安全清单**：Makefile 不引未审脚本。验：`make test-integration up` exit 0。
- [ ] 2.2 `test-integration up` 前置 `docker compose -p chatbiz down` 检查（production 互斥）。**安全清单**：fail 提示信息不含密码 / 敏感信息。验：production 起着时 `make test-integration up` 失败 + 提示"请先 `docker compose -p chatbiz down`"。
- [ ] 2.3 `test-integration test` 串行调：① `cd web/canvas && pnpm test:integration` ② `cd web/canvas && pnpm e2e:integration` ③ `cd web/admin && pnpm e2e:integration`。**安全清单**：每步超时 30min。验：退出码 0。
- [ ] 2.4 **验证**：2.1-2.3 跑通。`make test-integration up` + `make test-integration test` 全过（前提 1+3+4+5 节落地）。

## 3. LLM echo stub（audit-and-isolation 旁路）

- [ ] 3.1 修改 `services/audit-and-isolation/app/api/chat.py`：在 `chat_completions` handler 头部加旁路。若 `get_settings().environment == "integration"` 且 `body.get("model") == "echo-test"`，构造 OpenAI 兼容响应 `{"choices":[{"message":{"content":"ECHO: <last_user_msg>"}}],"usage":{"prompt_tokens":n,"completion_tokens":n,"total_tokens":n}}`，并**调用既有 audit enqueue 路径**写 `AuditLog`。**编码规范**：Python 异步 + SQLAlchemy；不新增外部依赖。**安全清单**：仅在 `ENVIRONMENT=integration` 时触发；production 路径不变。验：旁路代码分支 pytest 覆盖。
- [ ] 3.2 新增 `services/audit-and-isolation/tests/unit/test_chat_echo.py`：≥3 个 case（echo 响应 shape / model 白名单仅 `echo-test` / 审计埋点进 outbox）。**编码规范**：pytest + fakeredis（已有 dev 依赖）+ 异步。**安全清单**：不引真 LLM。验：`pytest services/audit-and-isolation/tests/unit/test_chat_echo.py` pass。
- [ ] 3.3 **验证**：3.1-3.2 跑通。`docker compose -p chatbiz-test up audit-and-isolation` + `curl -X POST http://localhost:8080/v1/chat/completions -H "X-Trace-Id: test-trace" -H "X-Model-Kind: private" -H "Authorization: Bearer dev" -d '{"model":"echo-test","messages":[{"role":"user","content":"hi"}]}'` 返回 `{"choices":[{"message":{"content":"ECHO: hi"}}]}`。**任务配对验证**：与 3.1-3.2 编码任务一一对应。

## 4. nginx healthz proxy + admin health URL 改相对路径

- [ ] 4.1 修改 `web/nginx.conf` 新增 `location /healthz { proxy_pass http://chatbiz-mcp:8080; }`（**注意容器内端口 8080**，不是 8004）。保留既有 `/health`（nginx self）。**编码规范**：与既有 location 块格式一致。**安全清单**：proxy 不暴露 mcp 内部 header（不 forward 敏感 header）。验：`curl http://localhost:5173/healthz` 返回 mcp 的 health 响应。
- [ ] 4.2 修改 `web/admin/src/api/health.ts` 的 `useHealth()` 默认 URL 改相对路径 `/healthz`；保留 `VITE_ADMIN_HEALTH_DIRECT=1` fallback 连 `http://localhost:8004/healthz`。**编码规范**：TypeScript 严格 + `import.meta.env` 显式声明。**安全清单**：默认值**不**硬编码 `http://localhost:8004`。验：`grep -n "localhost:8004" web/admin/src/api/health.ts` 仅在 `VITE_ADMIN_HEALTH_DIRECT` 分支命中。
- [ ] 4.3 **验证**：4.1-4.2 跑通。`docker compose -p chatbiz-test up` + `curl http://localhost:5173/healthz` 200 + admin SPA 在浏览器看到绿点。**任务配对验证**：与 4.1-4.2 编码任务一一对应。

## 5. canvas API 集成测试

- [ ] 5.1 新增 `web/canvas/vitest.integration.config.ts`：环境 `node` + include `tests/integration/**` + **exclude `e2e/**`** + timeout 30s + globalSetup 等 compose。**编码规范**：与 `vitest.config.ts` 单元配置**不**共享。**安全清单**：timeout 显式设上限，避免挂死。验：`cd web/canvas && pnpm test:integration` 启动。
- [ ] 5.2 新增 `web/canvas/tests/integration/global-setup.ts`：轮询 `http://localhost:5173/healthz` 直到 200（最长 60s）；超时则 `process.exit(1)`。**编码规范**：TypeScript 严格。**安全清单**：失败 fail 套件而非静默跑挂。验：故意把 5173 改错后 `pnpm test:integration` 60s 内 fail。
- [ ] 5.3 新增 `web/canvas/tests/integration/api-client.spec.ts`：≥4 case（登录成功返回 token / 列表查询 / 创建 workflow / 401 触发 security 边界 → 清 store 跳登录）。**注意**：apiClient 本身不抛 `WorkflowRuntimeError` / `UserError` 等 class；测试断言后端 `error_class` 字段和浏览器 redirect 行为。**编码规范**：TypeScript 严格 + 不引 `axios-mock-adapter` / `vi.mock`。**安全清单**：用真后端；测试数据独立 user。验：`pnpm test:integration` 全部 pass。
- [ ] 5.4 在 `web/canvas/package.json` 加 `"test:integration": "vitest run --config vitest.integration.config.ts"` script。**编码规范**：dependencies 不变。**安全清单**：script 不引可疑命令。验：`pnpm test:integration --help` 正常。
- [ ] 5.5 **验证**：5.1-5.4 跑通。`pnpm test:integration` 跑 ≥4 case 全 pass。**任务配对验证**：与 5.1-5.4 编码任务一一对应。

## 6. canvas E2E paul 财务月报（真实链路，简化版）

- [ ] 6.1 新增 `web/canvas/playwright.integration.config.ts`：baseURL `http://localhost:5173` + project `integration` + `testDir: './e2e/integration'` + **不设 webServer**（compose 外部起）+ `fullyParallel: true` + `retries: 1`。**编码规范**：与 `playwright.config.ts` 单元 mock 配置**不**共享。**安全清单**：不引未审 webServer 命令。验：`npx playwright test --config playwright.integration.config.ts --list` 列出 ≥3 spec。
- [ ] 6.2 新增 `web/canvas/e2e/integration/paul-monthly-report.spec.ts`：≥3 case（登录 → 建 workflow → 打开 editor → 验证持久化）。**不写 `page.route()` mock**；用独立 user（通过后端 API 生成 JWT 或复用 login 流程）。开头注释 `// critical-path-1: paul-monthly-report`。**编码规范**：TypeScript 严格 + `@playwright/test` API。**安全清单**：不 mock；测试数据独立 user。验：`npx playwright test --config playwright.integration.config.ts e2e/integration/paul-monthly-report.spec.ts` 全 pass。
- [ ] 6.3 在 `web/canvas/package.json` 加 `"e2e:integration": "playwright test --config playwright.integration.config.ts"` script。**安全清单**：不引未审命令。验：`pnpm e2e:integration --help` 正常。
- [ ] 6.4 **验证**：6.1-6.3 跑通。`pnpm e2e:integration` 跑 paul-monthly-report.spec.ts 全 pass；4 critical path ① 覆盖（verify 阶段 grep `// critical-path-1: paul-monthly-report` 注释）。**任务配对验证**：与 6.1-6.3 编码任务一一对应。

## 7. admin health E2E

- [ ] 7.1 新增 `web/admin/playwright.integration.config.ts`：baseURL `http://localhost:5173` + project `integration` + `testDir: './e2e/integration'` + **不设 webServer** + `fullyParallel: false`（admin health 是单一全局探针，多 worker 会互相干扰）。**编码规范**：与 `playwright.config.ts` 单元 mock 配置**不**共享。**安全清单**：不引未审 webServer 命令。验：`npx playwright test --config playwright.integration.config.ts --list` 列出 ≥3 spec。
- [ ] 7.2 新增 `web/admin/e2e/integration/admin-health.spec.ts`：≥3 case（绿点 / 停 mcp 看红点 / 启回 mcp 看恢复绿）+ access log 断言。**编码规范**：TypeScript 严格 + `@playwright/test` API。**安全清单**：不写 `page.route()` mock；access log 断言**不**写硬编码时间戳。验：`npx playwright test --config playwright.integration.config.ts e2e/integration/admin-health.spec.ts` 全 pass。
- [ ] 7.3 在 `web/admin/package.json` 加 `"e2e:integration": "playwright test --config playwright.integration.config.ts"` script。**安全清单**：不引未审命令。验：`pnpm e2e:integration --help` 正常。
- [ ] 7.4 **验证**：7.1-7.3 跑通。`pnpm e2e:integration` 跑 admin-health.spec.ts 全 pass；access log 断言通过。**任务配对验证**：与 7.1-7.3 编码任务一一对应。

## 8. 文档 + 验收

- [ ] 8.1 新增 `web/integration-tests/README.md`：开发命令（`make test-integration up/down/test/logs`）+ 排错（5173 端口被占 / mcp 不可达）+ 4 critical path 覆盖状态（① 100% / ②③④ spec 钩子）+ CI 接入指引（未来）。**编码规范**：中文。**安全清单**：不暴露 test 凭据（指向 `.env.test`）。验：手读通顺。
- [ ] 8.2 跑完整 `make test-integration test` 端到端一遍：① canvas vitest integration ≥4 case pass ② canvas playwright integration ≥3 case pass ③ admin playwright integration ≥3 case pass。**安全清单**：每步超时 30min 防挂死。验：退出码 0 + 4 critical path ① 100%。
- [ ] 8.3 **验证**：8.1-8.2 跑通。整套集成测试在干净 dev 机一次跑通（cold start ≤5min）。**任务配对验证**：与 8.1-8.2 文档/验收任务一一对应。

## 任务统计

- 编码任务：17（1.1 / 1.2 / 1.3 / 2.1 / 2.2 / 2.3 / 3.1 / 3.2 / 4.1 / 4.2 / 5.1 / 5.2 / 5.3 / 5.4 / 6.1 / 6.2 / 6.3 / 7.1 / 7.2 / 7.3 共 20，含 Makefile / compose 配置）
- 验证任务：8（1.4 / 2.4 / 3.3 / 4.3 / 5.5 / 6.4 / 7.4 / 8.3），**每个配对** ≥1 条编码任务的验证
- 文档任务：1（8.1）+ 端到端验收 1（8.2）
- **每条任务** 标注了"编码规范"和"安全清单"（openspec/config.yaml §tasks.rules 强制）
- 全部任务 ≤ 2h 粒度

## 与 proposal Non-goals 对齐

| Non-goal | 如何在本 tasks 中豁免 |
|---|---|
| 4 critical path ②③④ | 6.x 注释留 spec 钩子；本 change 不写 spec |
| LLM eval | 不写任务；后续 `llm-eval-baseline` change 接管 |
| 性能压测 | 不写任务；后续 `perf-regression-suite` change 接管 |
| CI 接入 | 不写任务；README 留指引 |
| production compose 改动 | 不动 `infrastructure/docker-compose.yml`；本 change 写到 `docker-compose-test.yml` |
| 既有 mock E2E 改动 | 不写任务；新 spec 在 `e2e/integration/` 独立目录 |
| paul 月报 E2E 不 run 到完成 | 6.2 明确简化为"创建 + 持久化"；run 链路作为后续增强 |
