# web-integration-test-suite — Brainstorm

> Raw capture of exploration thinking. `superpowers:brainstorming` skill 不可用，
> 按 fallback 手写 decision log。

---

## 背景与现状

当前 `web/` 下有两个前端：

```text
web/
├── canvas/          # workflow/chatflow 编辑器
│   ├── e2e/         # Playwright (auth/canvas/paul-monthly-report...)
│   └── tests/       # Vitest + jsdom (组件/钩子/store)
└── admin/           # 管理后台骨架
    ├── e2e/         # Playwright smoke（仅占位视图）
    └── tests/unit/  # Vitest smoke（14 菜单项）
```

后端已有 services：

```text
services/
├── credential           # 8000
├── workflow-engine      # 8001
├── mcp                  # 8004
└── audit-and-isolation  # 8080
```

统一入口由 `web/Dockerfile + nginx.conf` 提供，对外端口 `5173`：

```text
http://localhost:5173/        → portal
http://localhost:5173/canvas/ → canvas SPA
http://localhost:5173/admin/  → admin SPA
```

### 当前测试的问题

1. **canvas E2E 全部用 `page.route()` mock 后端**，没有真正打到 `workflow-engine`。
2. **admin E2E 只验证静态占位**，没有验证 health 探活连上 `services/mcp:8004/healthz`。
3. **没有统一测试启动矩阵**：跑一条“登录 → 建 workflow → 运行 → 看结果”的链路，需要手动起多个 service + db + redis。
4. **没有 API client 集成测试**：`web/canvas/src/lib/apiClient.ts` 的 axios 拦截器、401 跳转、错误分类只在单元测试里 mock。

---

## 3 个具名用户场景的“必中 wedge”

| 用户 | 场景 | 前端入口 | 后端链路 | 当前状态 |
|---|---|---|---|---|
| **paul** | 财务月报 workflow：登录 → 新建 workflow → 拖 LLM 节点 → 运行 → 看结果 | `/canvas/workflows` → `/canvas/workflows/:id/edit` → `/canvas/runs/:runId` | `credential` (登录) → `workflow-engine` (CRUD + run) → `audit-and-isolation` (LLM egress 审计) | `paul-monthly-report.spec.ts` 已存在，但全程 mock |
| **leo** | 数据查询/通道管理：配置 channel → 测试连通性 → 查状态 | 未来 `/admin/channels` 或 `/canvas/settings` | `channel-management` + `agent-runtime` | 服务尚未落地，**[FUTURE-IMPLEMENTATION]** |
| **anny** | 文档审核：上传合同 → 选择模板 → 触发审核 → 查看审批 | 未来 `/canvas/templates` + `/admin/approval` | `knowledge-base` + `manual-approval-flow` + `workflow-engine` | 服务尚未落地，**[FUTURE-IMPLEMENTATION]** |

本 change 先聚焦 **paul 财务月报端到端**，同时把 **admin health 探活** 和 **canvas API client 集成测试** 补齐。leo/anny 的链路在 spec 里留扩展点，等对应 service change 落地后再追加。

---

## 候选方案

### 方案 A：All-in Docker Compose E2E（推荐）

```text
┌─────────────────────────────────────────────────────────────────┐
│  Playwright (host)                                              │
│  └─▶ http://localhost:5173/canvas/ (nginx container)            │
│       └─▶ /api/nodes, /workflows, /runs  ▶ workflow-engine:8001 │
│       └─▶ /healthz  (portal/nginx 不代理，需 admin 直接调 mcp)   │
└─────────────────────────────────────────────────────────────────┘
```

启动命令：

```bash
cd infrastructure
docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d
# 等 healthy
cd ../web/canvas && pnpm e2e:integration
```

**优点：**
- 与生产部署形态一致（nginx + 后端 service）。
- 能覆盖 eng-review #11 的 4 条 critical path 中的 paul 财务月报。
- 一次 `docker compose up` 起所有依赖，可复现。

**缺点：**
- 重、慢；首次 cold start 可能 2-5 分钟。
- LLM 调用需要 mock 或接入测试网关，否则烧钱/不稳定。
- admin health 目前调 `localhost:8004/healthz`，在 nginx 容器外运行时需要 mcp 也在 host 暴露 8004；需要统一为 `/healthz` 走 nginx proxy 或环境变量注入。

### 方案 B：三层金字塔（单元 + API 集成 + 少量 E2E）

```text
        ┌─────────────┐
        │  Playwright │  ← 少量黄金路径 E2E（paul 月报、admin health）
        │   5-10 条   │
        └──────┬──────┘
               │
        ┌──────┴──────┐
        │  API 集成测试 │  ← axios + 真实后端（Testcontainers / compose）
        │  20-30 条    │
        └──────┬──────┘
               │
        ┌──────┴──────┐
        │  单元测试     │  ← 已存在，继续保留
        └─────────────┘
```

**优点：**
- 与 eng-review #10 的“3 层测试 + LLM eval”对齐。
- API 集成比全 E2E 快、稳，能覆盖错误边界分类。

**缺点：**
- 需要额外写 API client 的集成测试框架。
- 仍然需要 compose 起后端。

### 方案 C：MSW / Playwright route 保持 mock

** rejected：** 不满足“完整集成测试”目标。mock 只能验证 UI 状态转换，无法发现后端 schema 漂移、CORS、proxy、鉴权等问题。

---

## Rejected Alternatives

| 方案 | 拒绝理由 |
|---|---|
| C. 保持 mock | 与“前端到后端的完整集成测试”目标冲突；无法覆盖 proxy/nginx/后端真实响应 |
| 每个前端单独一个 docker-compose 端口测试 | 违反 CLAUDE.md 已写入的“单端口 5173”约定，且造成端口冲突和重复环境 |
| 用 Jest 替换 Vitest | 仓库已统一 Vite 生态，引入 Jest 增加概念；Vitest + Playwright 已满足三层金字塔 |
| 直接在 `web/canvas/e2e/*.spec.ts` 里改真实后端 | 现有 mock 测试仍有价值（快速反馈、无依赖），应新增 `e2e/integration/` 目录而非替换 |

---

## 关键决策（初步）

### D1：测试分层 = 单元 + API 集成 + E2E

**原因：** eng-review #10 已锁定“3 层测试 + LLM eval”；本 change 不发明新分层，只把现有 layer 补齐。

### D2：E2E 使用统一入口 `http://localhost:5173`

**原因：** CLAUDE.md 已约定单端口；Playwright 测 canvas 和 admin 都从 portal 进，确保 nginx 路径分发也被覆盖。

### D3：admin health 调用统一为 `/healthz` 走 nginx proxy 到 mcp

**原因：** 当前 `useHealth()` 默认 `http://localhost:8004/healthz`，在 docker 里浏览器无法直接访问容器外端口。需要 nginx.conf 增加：

```nginx
location /healthz {
    proxy_pass http://chatbiz-mcp:8004;
}
```

或改 admin 通过相对路径 `/healthz` 调用。这是实现 detail，design 阶段再定。

### D4：LLM 节点在 E2E 中 mock

**原因：** 真实 LLM 调用贵、慢、不稳定；但审计链路（请求是否经过 audit-and-isolation）可以测。用一个测试专用的“echo LLM”或 stub 替换。

---

## 风险与 Open Questions

### 风险

1. **admin-web → admin 全仓替换副作用**：把 change 名 `admin-web-bootstrap` 也可能误改成了 `admin-bootstrap`。apply 前需 `grep -R "admin-bootstrap" openspec/` 修正。
2. **canvas 现有 Playwright 测试数量多**，全部改成真实后端工作量大；需要识别哪些是 pure UI 测试（保留 mock），哪些是关键路径（改 integration）。
3. **`workflow-engine` 在 `docker-compose-dev.yml` 里直接定义而非 `extends`**，且 `mcp` 服务可能还没加进 dev compose，需要补齐。
4. **Playwright 并发 vs 后端数据库状态**：多个 test worker 同时写 workflow 会互相干扰；需要每个 test 用独立 tenant/user 或 truncate 数据。

### Open Questions

1. **OQ1：E2E 测试数据如何隔离？** 是每个 test 新建独立 workflow，还是跑前 seed 固定数据？
2. **OQ2：LLM 节点用 echo stub 还是直接 mock workflow-engine 的 `/runs/:id/result`？**
3. **OQ3：admin health 探活是只验证绿点出现，还是验证 5s 轮询真实打到 mcp `/healthz`？**
4. **OQ4：是否需要在 CI 中跑这套集成测试？当前仓库没有 CI，这是后续 change 还是本 change 一起建？**
5. **OQ5：API 集成测试放在 `web/canvas/tests/integration/` 还是新建 `services/workflow-engine/tests/frontend-contract/`？**

---

## 与 eng-review 锁定决策的映射

| eng-review finding | 本 change 如何覆盖/对齐 |
|---|---|
| #10 三层测试 + LLM eval | 明确采用单元/API/E2E 三层；LLM eval 用 echo stub 覆盖非 LLM 输出质量部分 |
| #11 4 条 critical path 100% | paul 财务月报 E2E 是重点；网关 PII、人工审批、插件降级需后续 service 落地后补 |
| #9 4 边界错误处理 | API 集成测试覆盖 401/403/5xx/timeout 到 UI 错误边界 |
| #12 存储量预估 | 测试本身不产生持久数据；测试数据清理策略在 design 中明确 |

---

## 下一步建议

1. 写 `proposal.md`：明确 scope = “web/ 集成测试基础设施 + paul 月报 E2E + admin health E2E + API 集成测试框架”。
2. 写 `design.md`：确定 compose 启动矩阵、测试数据隔离、LLM stub 方案、nginx healthz proxy。
3. 写 `specs/`：拆成 `web-e2e-orchestration`、`canvas-api-integration`、`admin-health-integration` 等 capability。
4. 等用户确认 OQ1-OQ5 后再进 `tasks/plan`。

---

## 备注

- 本 change **不写代码**，只产出 OpenSpec artifacts。
- 当前 `mcp-server-management-ui` 仍在 in-progress，它的前端视图会挂载到 `/admin/mcp-tools`，本 change 的 admin health E2E 为它留好扩展 hook。
