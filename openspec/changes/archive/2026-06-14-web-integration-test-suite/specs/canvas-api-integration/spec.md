# canvas-api-integration

**Frontend Scope: 含前端**（`web/canvas/tests/integration/api-client.spec.ts` + `web/canvas/vitest.integration.config.ts` + `web/canvas/tests/integration/global-setup.ts`）

**Backend Scope: 不新增后端**（消费既有 `services/credential` / `services/workflow-engine` API）

**Impact**（被谁消费）：
- 被 `web-e2e-orchestration` 消费（共享 test compose 启动矩阵）
- 被 canvas 后续 change 消费（apiClient 演进时新增 case 即可）
- 验证 eng-review **Quality #3** 错误处理 4 边界（canvas drag / runtime / user / security）的后端 `error_class` 字段可被前端识别

## ADDED Requirements

### Requirement: API 集成测试覆盖 4 类核心 axios 场景

`web/canvas/tests/integration/api-client.spec.ts` MUST 跑 ≥4 个 `it()` case 真打 test compose 后端：

1. `POST /api/auth/login` 成功（200 + token）
2. `GET /workflows` 列表查询
3. `POST /workflows` 创建 workflow
4. 401 未授权 → apiClient 触发 security 边界处理（清 store + 跳登录）

每个 case MUST 用真后端（`workflow-engine:8001` / dev IAM login 端点），**禁止**用 `axios-mock-adapter` 或 `vi.mock`。

#### Scenario: 登录成功返回 token
- **WHEN** apiClient 调 `POST http://localhost:5173/api/auth/login` 含 `{username, password}`
- **THEN** MUST 返回 200 + JSON body 含 `token` 与 `user`
- **AND** apiClient 把 `Authorization: Bearer <token>` 注入后续请求

#### Scenario: 401 触发 security 边界
- **WHEN** apiClient 调任意受保护 API 但 token 缺失 / 过期
- **THEN** MUST 收到 401 响应
- **AND** apiClient MUST 触发 security 边界处理：清 store + 跳 `/login?redirect=<原 url>`（eng-review Quality #3 security 边界）

#### Scenario: 400 参数不全映射到 user 边界
- **WHEN** apiClient 调 `POST /workflows` 缺必填字段 `name`
- **THEN** workflow-engine MUST 返回 422 / 400 并带 `error_class = "user"`
- **AND** 响应 body MUST 含字段名（如 `"name is required"`）

### Requirement: Vitest integration config 区分单元与集成

`web/canvas/vitest.integration.config.ts` MUST 独立于单元配置（`vitest.config.ts`）：
- `test.environment: 'node'`（**非** jsdom，因为测的是 axios HTTP 而非 DOM）
- `test.include: ['tests/integration/**/*.spec.ts']`（**不**吞 `tests/unit/` 或 `e2e/`）
- `test.exclude: ['e2e/**', 'node_modules/**', 'dist/**']`（**显式排除 e2e**，避免与 playwright 冲突）
- `test.testTimeout: 30_000`
- `test.hookTimeout: 30_000`
- `test.globalSetup: ['./tests/integration/global-setup.ts']` —— 等 compose healthy 才开跑

`pnpm` scripts MUST 新增 `test:integration`：`vitest run --config vitest.integration.config.ts`。

#### Scenario: 跑集成测试独立于单元
- **WHEN** 在 `web/canvas` 跑 `pnpm test`（单元）
- **THEN** MUST 只跑 `tests/unit/**`，**不**触发 integration spec

- **WHEN** 在 `web/canvas` 跑 `pnpm test:integration`
- **THEN** MUST 只跑 `tests/integration/**`，**不**触发 unit spec

#### Scenario: globalSetup 等 compose healthy
- **WHEN** `pnpm test:integration` 启动
- **THEN** globalSetup MUST 轮询 `http://localhost:5173/healthz` 直到 200（最长 60s）
- **AND** 若超时则 fail 整个套件而非跑挂的 case

### Requirement: 测试数据用独立 user 不污染 dev

每个 spec MUST 在 `beforeAll` 创建独立 `user_id = uuid`（当前后端无 `tenant_id`，用 `user_id` 隔离），创建独立 `workflow`；`afterAll` 删除该 user 创建的所有 workflow。**禁止**写全局 fixture / seed。

#### Scenario: spec 间 user 隔离
- **WHEN** spec A 创建 workflow W1（user U_A）
- **AND** spec B 创建 workflow W2（user U_B）
- **THEN** spec A 调 `GET /workflows` MUST 仅返回 W1
- **AND** spec B 调 `GET /workflows` MUST 仅返回 W2

#### Scenario: teardown 清理
- **WHEN** spec 完成
- **THEN** `afterAll` MUST 调 `DELETE /workflows?created_by=<user_id>` 或直接 SQL 删除该 user 的 workflows
- **AND** 该 user 的 workflow MUST 不出现在后续 spec 的列表中

### Requirement: 覆盖率绑定（specs.rules 100% 接口覆盖）

集成测试 MUST 覆盖 `web/canvas/src/lib/apiClient.ts` 100% 公共方法（`request` / `get` / `post` / `put` / `delete` —— axios 实例方法）+ 100% 拦截器分支（401 清 store 跳登录）。`vitest.integration.config.ts` MUST 配置 `coverage.include: ['src/lib/apiClient.ts']` + `coverage.thresholds: { lines: 100, branches: 100, functions: 100, statements: 100 }`。

#### Scenario: 覆盖率门槛
- **WHEN** 跑 `pnpm test:integration --coverage`
- **THEN** `apiClient.ts` 行覆盖 / 分支覆盖 / 函数覆盖 / 语句覆盖 MUST 全部 100%
- **AND** 低于 100% MUST fail 整个套件
