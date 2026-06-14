# admin-health-integration

**Frontend Scope: 含前端**（`web/admin/src/api/health.ts` 改默认 URL + `web/admin/e2e/integration/admin-health.spec.ts` + `web/nginx.conf` 新增 location）

**Backend Scope: 不新增后端**（消费既有 `services/mcp:8080/healthz`，经 nginx proxy）

**Impact**（被谁消费）：
- 被 `web-e2e-orchestration` 消费（共享 test compose + nginx）
- 被 `mcp-server-management-ui` change 消费（admin Web 容器化后 health 探活是必备探针）
- 后续运维/监控接入（验证 admin 容器启动后能感知后端服务可用性）

## ADDED Requirements

### Requirement: admin health 走 nginx `/healthz` 相对路径

`web/admin/src/api/health.ts` 的 `useHealth()` MUST 默认 fetch 相对路径 `/healthz`（**非** `http://localhost:8004/healthz`）。`web/nginx.conf` MUST 新增 `location /healthz { proxy_pass http://chatbiz-mcp:8080; }` 让 admin 容器化后能通过 nginx 代理访问 mcp。**保留** `VITE_ADMIN_HEALTH_DIRECT=1` 显式开关允许 dev 阶段直连 host 8004（向后兼容）。**注意**：mcp 容器**内部**监听 8080，nginx proxy 用容器内 DNS + 8080。

#### Scenario: 容器内 admin 走 nginx
- **WHEN** admin Web 容器（5173）启动，浏览器 fetch `/healthz`
- **THEN** nginx MUST 代理到 `chatbiz-mcp:8080/healthz` 并返回 mcp 的 health 响应
- **AND** 前端 useHealth 看到 status: "healthy"

#### Scenario: dev 阶段直连 host 仍工作
- **WHEN** 开发者本地 `VITE_ADMIN_HEALTH_DIRECT=1 pnpm dev`（不经过容器）
- **THEN** useHealth fetch `http://localhost:8004/healthz` 直连 mcp
- **AND** 仍返回 status: "healthy"

#### Scenario: 默认 URL 不再硬编码 host 端口
- **WHEN** 读 `web/admin/src/api/health.ts` 源码
- **THEN** MUST 不含 `http://localhost:8004` 字面量（除了 `VITE_ADMIN_HEALTH_DIRECT` 分支）
- **AND** MUST 含 `import.meta.env.VITE_ADMIN_HEALTH_DIRECT` 判断

### Requirement: 集成 E2E 验证 health 探活端到端

`web/admin/e2e/integration/admin-health.spec.ts` MUST 跑 ≥3 个 Playwright `test()` case：
1. 打开 `/admin` → header bar 显示绿点（健康）
2. 模拟 mcp 短暂不可用（用 `docker compose -p chatbiz-test stop mcp`）→ header bar 显示红点（不健康）
3. mcp 恢复后 → header bar 在下次轮询（≤5s）显示回绿点

**额外断言**：测试期间 `mcp` 容器的 access log MUST 含 `GET /healthz` 请求 ≥1 条（验证 nginx 真的代理过去，**不**是前端在 mock）。

#### Scenario: 绿点出现
- **WHEN** Playwright 打开 `http://localhost:5173/admin/`
- **THEN** page header bar MUST 显示绿点（`aria-label="服务健康：健康"`）
- **AND** 元素 MUST 在 5s 内出现（轮询响应）

#### Scenario: 红点出现
- **WHEN** mcp 容器被 `docker compose -p chatbiz-test stop mcp` 停掉
- **AND** Playwright 等待 ≤10s
- **THEN** header bar MUST 切换到红点（`aria-label="服务健康：不可用"`）

#### Scenario: 恢复绿点
- **WHEN** mcp 容器被 `docker compose -p chatbiz-test start mcp` 启回
- **AND** Playwright 等待 ≤10s
- **THEN** header bar MUST 切回绿点（轮询触发）

#### Scenario: nginx 真的代理（access log 断言）
- **WHEN** admin-health.spec.ts 跑完
- **THEN** `docker compose -p chatbiz-test logs mcp` MUST 含 `GET /healthz` 至少 1 条
- **AND** 测试若**无**access log 记录则 fail（防止前端在 mock 假绿点）

### Requirement: Playwright 5s 轮询配置

`useHealth()` MUST 用 SWR `refreshInterval: 5000`（5s 轮询，与 admin-bootstrap 既有 spec 一致）。E2E spec MUST 等轮询周期后再断言（避免 race condition）。

#### Scenario: 5s 轮询
- **WHEN** admin 页面打开后 5s
- **THEN** mcp container 的 access log MUST 含**至少 2 条** `GET /healthz`（初始 + 1 次轮询）

#### Scenario: 关闭页面停止轮询
- **WHEN** page 关闭（`page.close()`）
- **THEN** SWR MUST 停止轮询（`refreshWhenHidden: false` 默认行为）
- **AND** mcp access log 在 page close 后 10s 内**不**新增 `/healthz` 请求

### Requirement: 错误处理 —— mcp 完全不可达不崩前端

`useHealth()` MUST 在 mcp 完全不可达时返回 `status: "down"`（不抛 exception）；header bar MUST 显示红点；admin 页面其他功能 MUST 仍可访问（不被 health 失败拖垮）。

#### Scenario: mcp 不可达不崩
- **WHEN** mcp 容器从 compose 移除（`docker compose -p chatbiz-test rm -f mcp`）
- **AND** Playwright 打开 `/admin/`
- **THEN** page MUST 不抛 unhandled exception
- **AND** header bar MUST 显示红点
- **AND** 其他菜单项点击 MUST 仍响应（如 `/workflow` 跳占位视图）
