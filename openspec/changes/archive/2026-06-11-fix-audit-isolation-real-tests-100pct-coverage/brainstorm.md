# Brainstorm — fix-audit-isolation-real-tests-100pct-coverage

## 背景

本 change 是 `workflow-engine 100% coverage` 之后的显式 follow-up。用户已明确选择执行 `fix-audit-isolation-real-tests-100pct-coverage`，目标是在现有 `services/audit-and-isolation` 基础上补齐真实测试与覆盖率门禁，使数据隔离网关达到 100% 单元/关键路径覆盖。

相关 source of truth：

- `docs/architecture.md`：ChatBiz 6 层架构、数据隔离网关作为 LLM egress 强制点。
- `docs/prd.md`：MVP 包含数据隔离网关 + paul 财务月报 workflow + 基础审计。
- 已锁定 eng-review findings：
  - #1 数据隔离网关 = egress 强制点，2 实例 HA + 健康检查 + 跨网关 trace-id。
  - #9 错误处理 4 边界：canvas / runtime / user / security。
  - #10 3 层测试 + LLM eval。
  - #11 4 critical path 100% 覆盖，其中 #2 是网关 PII 拦截。

## 当前状态探索

`services/audit-and-isolation` 已经不是空服务，当前结构包括：

- `app/api/chat.py`：OpenAI-compatible `/v1/chat/completions` 主链路。
- `app/api/health.py`：`/healthz` / `/readyz`。
- `app/api/models.py`：`/v1/models`。
- `app/pii/*`：6 类 PII 规则、检测、脱敏、还原。
- `app/audit/*`：prompt hash + AuditOutbox。
- `app/llm/*`：上游 LLM 调用与 streaming helper。
- `app/routing/*`：model routing Redis/内存缓存与 dispatcher。
- `app/credential_client.py`：通过 credential service 获取 LLM API key。
- `app/database.py` / `app/redis_client.py`：基础设施封装。

现有测试：

- `tests/unit/`：auth、errors、api_chat、llm_client、alerts、audit_writer、pii_rules、dispatcher、credential_client。
- `tests/integration/`：audit log、credential down、4 个 e2e 场景、PII critical path 2.1-2.8、routing table、redact/reverse。

当前 baseline：

```text
127 passed
TOTAL 714 stmts / 140 missing = 80% coverage
```

主要缺口：

- `app/api/health.py`：39%，readyz 分支未充分覆盖。
- `app/api/models.py`：64%，list_models 未覆盖。
- `app/main.py`：61%，lifespan 未覆盖。
- `app/database.py`：50%，lazy engine/session/get_session/dispose 未覆盖。
- `app/llm/streaming.py`：0%。
- `app/models/llm.py`：0%。
- `app/api/chat.py`：85%，若干错误与边缘分支未覆盖。
- `app/llm/client.py`：84%，流式路径与不可达兜底缺口。
- `app/credential_client.py`：97%，不可达兜底缺口。
- `app/pii/redactor.py` / `reverser.py` / `rules.py` / `redis_client.py`：少量边界分支。

## 决策链

### Q1: 本 change 是否允许修改产品代码？

决策：允许，但只允许小而明确的测试性/健壮性修正，不做功能扩展。

理由：上一个 `workflow-engine` 100% coverage change 已证明，有些缺口来自真实 bug 或不可达防御行。为了坚持“真实测试”而不是 artificial monkeypatch，可以对不可达兜底、错误映射、序列化等做最小修复。

边界：

- 可以修复已被测试暴露的 bug。
- 可以给真正不可达的防御性兜底加 `# pragma: no cover`，但必须在 `verify.md` 逐项说明原因。
- 不得重写网关架构、PII 规则语义、credential 协议、路由策略。

### Q2: 100% 覆盖以哪条命令为准？

决策：以 pytest-cov 为主门禁，同时保留现有 `verify.py`。

目标命令：

```bash
cd services/audit-and-isolation
PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100
python3 verify.py
```

原因：`pyproject.toml` 已定义 `--cov=app --cov-fail-under=100`，README 也把服务测试栈描述为 pytest + unittest/fakeredis/respx。现有 `verify.py` 仍使用 unittest discover，适合作为兼容 CI gate，但覆盖率门禁应显式跑 pytest-cov。

### Q3: 测试策略如何组织？

决策：采用“缺口驱动 + 真实路径优先 + 精确 patch 外部边界”的策略。

测试优先覆盖：

1. 直接补整块未覆盖模块：health/models/main/database/redis/streaming/models_llm。
2. 补 chat.py 主链路边缘分支：missing model、header invalid、PII fail-closed、Upstream5xx/429/generic、message/response 内容跳过、usage 缺失。
3. 补 PII redactor/reverser/rules 边界：Redis 写失败、invalid JSON map、USCC helper 边界。
4. 处理不可达兜底：credential_client 与 llm/client 中 loop 后兜底。

外部依赖处理：

- PostgreSQL：单元测试不连真实 PG，使用 async fake session/engine 或 monkeypatch `get_session`。
- Redis：用 fake async Redis 或 monkeypatch `redis_client.get_redis`。
- credential service / upstream LLM：使用 respx 或直接 patch imported binding。
- AuditOutbox：用 fake outbox 捕获 enqueue，不写真实 DB。

### Q4: 是否把 3 个具名用户场景都纳入本 change？

决策：本 change 不新增三场景业务 e2e，但在设计上明确它服务于 3 个必中 wedge。

映射：

- paul 财务月报：公有模型调用必须经 PII 脱敏 + metadata-only audit。
- leo 基础服务数据查询：私有/内网模型可 bypass，但必须保留 trace/audit。
- anny 文档审核：RAG/合同文本中的邮箱、企业统一社会信用代码、金额必须脱敏。

本 change 的直接验收仍聚焦 `audit-and-isolation` 服务的 gateway critical path，不扩展 agent-runtime/knowledge-base/canvas 端到端。

## 可选方案与取舍

### 方案 A：只补测试，不动产品代码

优点：风险最低，符合“coverage follow-up”的直觉。

缺点：不可达兜底行会迫使测试用极度 artificial 的 monkeypatch；如果测试暴露真实 bug，也无法修复，会让 100% 覆盖变成形式主义。

结论：拒绝。`workflow-engine` follow-up 已证明“小产品修复 + 明确记录”更可靠。

### 方案 B：真实测试优先 + 最小产品修复/pragma（推荐）

优点：覆盖率目标可达，测试仍保持真实路径，产品 bug 可被修正；与上一个 change 的执行方式一致。

缺点：需要严格控制产品改动范围，避免 coverage change 演变成功能开发。

结论：采用。

### 方案 C：重构测试框架，引入统一 pytest fixtures

优点：长期可维护性最好，能减少 unittest patch 重复。

缺点：改动面大，容易同时改变 127 个已有测试的行为；不是本 follow-up 的最短路径。

结论：本轮拒绝。仅在新增测试中局部抽取 helper，不做全局迁移。

## 设计概要

### 范围内

- 为 `services/audit-and-isolation` 新增/扩展测试，使 `app` coverage 达到 100%。
- 明确覆盖 PII 拦截 critical path 2.1-2.8 既有测试不回退。
- 补齐 metadata-only audit、安全失败路径、credential/Redis/upstream 降级测试。
- 必要时对产品代码做最小修复或不可达 pragma，并在 verify/retrospective 中说明。
- 更新服务 `verify.py`，让覆盖率门禁成为显式 CI gate（如果现有 verify.py 未跑 coverage）。

### 范围外

- 不新增网关 API 功能。
- 不改变 PII 类型集合或脱敏占位符格式。
- 不实现 K8s 真实 2 实例 HA 测试，只验证 health/readiness 与 Redis 共享 map 语义。
- 不实现跨服务 paul/leo/anny 全链路 E2E；仅保证网关服务的关键路径。
- 不引入真实 LLM / credential / Redis / PostgreSQL 外部依赖到单元测试。

## 风险

1. **coverage 命令执行目录风险**：必须从 `services/audit-and-isolation` 运行，或显式设置 `PYTHONPATH` / coverage source，否则 pytest rootdir 会跑偏。
2. **unittest + pytest-cov 混用风险**：现有测试是 unittest 风格，新增 pytest 异步测试要与 `asyncio_mode=auto` 兼容。
3. **AsyncMock 未 await warning**：现有 `test_audit_writer.py` 已出现 warning，应在本 change 中消除，避免掩盖真实异步写入问题。
4. **不可达兜底行风险**：如果强行测试不可达分支，会让测试变脆。更合理做法是重构或 pragma，并解释。
5. **敏感数据风险**：测试 fixture 不得引入真实 API key；PII 使用规范化假数据。

## Open Questions

1. 是否要求把 `verify.py` 从 unittest discover 切到 pytest-cov？默认决策：是，作为本 change 的主要质量门禁。
2. 是否允许对不可达兜底行使用 `# pragma: no cover`？默认决策：允许，但仅限确认为控制流不可达且在 `verify.md` 记录的行。
3. 是否需要把 README 中 `/v1/completions` 与实际 router 不一致一并修正？默认决策：不纳入本 change，除非测试/OpenAPI 门禁直接失败。

## 验收标准

- `services/audit-and-isolation` 下 pytest 全量通过。
- `--cov=app --cov-fail-under=100` 通过。
- `python3 verify.py` 通过。
- PII critical path 2.1-2.8 保持通过。
- security grep 保持通过：API key / private key / 明文 prompt 不落库。
- `verify.md` 记录真实命令、退出码、覆盖率表、产品代码修复/pragma 清单。
