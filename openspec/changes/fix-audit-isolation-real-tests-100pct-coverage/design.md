## Context

`audit-and-isolation` 是 ChatBiz 的数据隔离网关，位于调用方与外部 LLM provider 之间，是 `docs/architecture.md` §4 中模型与集成层的 egress 强制点。eng-review #1 已锁定：所有 LLM 调用必须经过该网关，网关需具备 2 实例 HA、健康检查与跨网关 trace-id 关联。eng-review #9/#10/#11 又锁定错误边界、3 层测试以及 4 critical path 100% 覆盖，其中本服务负责 critical path #2：网关 PII 拦截。

当前服务已经实现 OpenAI-compatible `/v1/chat/completions`、PII detect/redact/reverse、metadata-only audit、credential service API key 获取、Redis 路由缓存、health/readiness 与 model list。现有测试 127 个全部通过，但 `pytest --cov=app` baseline 约 80%。主要缺口集中在非主 happy-path：`app/api/health.py`、`app/api/models.py`、`app/main.py`、`app/database.py`、`app/llm/streaming.py`、`app/models/llm.py`，以及 `chat.py` 的错误分支。

本 change 是 coverage follow-up，不重新讨论网关架构，不改变已锁定产品行为。

## Goals / Non-Goals

**Goals:**

- 让 `services/audit-and-isolation` 达到 `app` 100% pytest-cov 覆盖。
- 保持并显式验证 PII critical path 2.1-2.8。
- 覆盖 metadata-only audit、安全失败、credential down、Redis 降级、upstream 5xx/timeout/429/generic 等网关关键失败姿态。
- 补齐 health/readiness、model list、lifespan、database/redis client、streaming、LLM schema 的直接测试。
- 将 coverage gate 纳入 `verify.py`，形成可重复 release gate。
- 若发现真实 bug，做最小产品修复并在 `verify.md` / `retrospective.md` 记录。

**Non-Goals:**

- 不新增或改变 `/v1/chat/completions`、`/v1/models`、`/healthz`、`/readyz` 的外部 API。
- 不改变 PII 类型集合、占位符格式、TTL 或 model routing 策略。
- 不实现真实 K8s 2 实例 failover 压测；仅验证 readiness 和 Redis 共享状态语义。
- 不做跨服务 paul/leo/anny 端到端联调；本 change 只覆盖网关服务。
- 不引入真实 LLM、真实 credential service、真实 Redis、真实 PostgreSQL 到单元测试。
- 不把 unittest 测试体系整体迁移到 pytest fixture 架构。

## Decisions

### D1：采用“真实测试优先 + 最小产品修复/pragma”

- **选择**：以真实业务路径和外部边界 mock 为主补覆盖；仅当覆盖缺口来自真实 bug 或控制流不可达防御行时，允许小范围产品代码修复或 `# pragma: no cover`。
- **理由**：`workflow-engine` 100% coverage follow-up 已验证，仅靠 artificial monkeypatch 会让测试脆弱。网关是合规关键路径，测试应证明产品行为，而不是覆盖率数字游戏。
- **已考虑 alternative**：
  - 只补测试不动产品代码：拒绝。不可达兜底行会导致测试失真。
  - 大规模重构代码以利测试：拒绝。本 change 是 follow-up，不是架构重写。

### D2：pytest-cov 是主门禁，`verify.py` 是聚合门禁

- **选择**：主验收命令为：
  ```bash
  cd services/audit-and-isolation
  PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100
  python3 verify.py
  ```
- **理由**：`pyproject.toml` 已配置 pytest coverage，README 已把测试栈描述为 pytest + unittest/fakeredis/respx。现有 `verify.py` 18 项检查应保留，但需要显式包含 coverage gate。
- **已考虑 alternative**：继续只用 `unittest discover`：拒绝。它无法证明覆盖率达标。

### D3：测试组织按模块缺口新增，不做全局测试框架迁移

- **选择**：新增聚焦测试文件：`test_api_health.py`、`test_api_models.py`、`test_main_lifespan.py`、`test_database.py`、`test_redis_client.py`、`test_llm_streaming.py`、`test_models_llm.py`，并扩展现有 `test_api_chat.py`、`test_audit_writer.py`、`test_llm_client.py`、`test_credential_client.py`、PII redactor/reverser 测试。
- **理由**：当前 127 个测试已稳定，通过增量补缺口风险最小。
- **已考虑 alternative**：抽一个全局 `conftest.py` 重写 fixture：拒绝。收益长期存在，但本轮会扩大改动面。

### D4：外部依赖只在边界 fake/mock

- **选择**：PG/Redis/credential/upstream LLM 全部通过 fake async 对象、respx、monkeypatch imported binding 处理，不依赖真实服务。
- **理由**：100% 单元覆盖应稳定、快速、离线；真实外部依赖属于 e2e/compose gate。
- **已考虑 alternative**：使用 docker-compose 跑真实 PG/Redis：拒绝。会让 coverage gate 变慢且不稳定。

### D5：三类用户 wedge 以网关行为映射，不扩展跨服务 E2E

- **选择**：测试中覆盖 paul/leo/anny 对应的网关语义，而不是全链路业务流程：
  - paul 财务月报：公有模型 + PII redaction + audit。
  - leo 数据查询：私有模型 + bypass + trace/audit。
  - anny 文档审核：邮箱/信用代码/营收金额脱敏。
- **理由**：本服务是共用 egress 网关，跨服务编排属于 workflow-engine/agent-runtime/knowledge-base 后续范围。
- **已考虑 alternative**：本 change 直接补 3 个端到端用户流程：拒绝。scope 过大，且会引入未完成服务依赖。

### D6：不可达兜底必须显式记录

- **选择**：若 `credential_client.py` 或 `llm/client.py` 的 loop 后兜底无法由真实控制流触达，则优先重构为可测试结构；无法合理重构时加 `# pragma: no cover`，并在 `verify.md` 列出文件、行、理由。
- **理由**：不可达防御行不应驱动 artificial 测试；但 coverage 排除必须透明。
- **已考虑 alternative**：patch `range()` 或构造不可能状态执行兜底：拒绝。测试语义差且易碎。

## Risks / Trade-offs

- [Risk] coverage 命令从仓库根运行会导致 `tests/` 路径找不到或 coverage source 错误 → Mitigation: 所有文档和 `verify.py` 明确 `cwd=services/audit-and-isolation`，必要时设置 `PYTHONPATH=.`。
- [Risk] unittest + pytest-asyncio 混用导致事件循环/AsyncMock warning → Mitigation: 新增异步测试使用 `pytest.mark.asyncio` 或 `unittest.IsolatedAsyncioTestCase`；修复现有未 await warning。
- [Risk] 100% 覆盖诱导过度 patch 内部实现 → Mitigation: 优先测 public function/API 行为；patch 仅限外部 I/O 与 imported binding。
- [Risk] 产品修复越界成行为变更 → Mitigation: 所有产品代码改动必须能用失败测试解释，且在 `verify.md` 标注。
- [Trade-off] 不跑真实 PG/Redis/LLM 会降低集成真实性 → 接受理由：本 change 是单元覆盖门禁；现有 integration/critical path 仍覆盖核心语义，真实 compose gate 可后续单独做。

## Migration Plan

1. 创建并完成 OpenSpec artifacts：proposal、design、delta specs、tasks、plan。
2. 运行 baseline coverage，记录缺口。
3. 按模块新增/扩展测试，逐轮运行 `pytest --cov=app --cov-fail-under=100`。
4. 对测试暴露的产品 bug 做最小修复；对真实不可达防御行做重构或 pragma。
5. 更新 `verify.py` 纳入 pytest-cov gate，并确保原 18 项检查不回退。
6. 写 `verify.md`：记录命令、退出码、覆盖率、测试数量、产品代码改动/pragma 清单。
7. 写 `retrospective.md`：记录 gotchas 与后续改进。

Rollback：本 change 不涉及 DB schema/API/部署变更。若失败，可回滚新增测试、`verify.py` coverage gate 与少量 app 修复；服务运行行为不应受影响。

## Open Questions

1. README 中列出的 `POST /v1/completions` 与当前 router 不一致，本 change 默认不修；若 OpenAPI/verify 直接失败，再单独处理。
2. 不可达兜底采用重构还是 pragma 需以实际 coverage report 与代码可读性决定。
3. 是否将 `verify.py` 原 unittest discover 完全替换为 pytest，还是在现有 18 项前增加 pytest-cov gate？默认选择后者以降低风险。
