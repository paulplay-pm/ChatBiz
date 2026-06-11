## Why

`audit-and-isolation` 是 eng-review #1 锁定的 LLM egress 强制点，也是 MVP 数据隔离与基础审计的核心服务。当前 `workflow-engine` 已达到 100% 覆盖，但网关服务 pytest-cov baseline 仅约 80%，仍存在 health/readiness、模型列表、lifespan、database/redis 封装、streaming、LLM schema、chat 错误分支等缺口。现在补齐 100% 真实测试，可把 PII 拦截 critical path、metadata-only audit、credential/Redis/upstream 降级路径变成可回归的 release gate。

## What Changes

**audit-and-isolation 测试门禁**
- From: 服务已有 127 个 unittest/集成测试与 8 个 PII critical path 子场景，但 pytest-cov `app` 覆盖率约 80%，`verify.py` 未显式执行 coverage gate。
- To: 新增/扩展真实单元测试与必要的最小产品修正，使 `python3 -m pytest tests/ --cov=app --cov-fail-under=100` 与 `python3 verify.py` 均通过。
- Reason: 对齐 eng-review #10/#11 的 3 层测试与 4 critical path 100% 覆盖要求。
- Impact: 非破坏性；影响 `services/audit-and-isolation/tests/`、少量 app 防御性分支、`verify.py`。

**关键路径与安全分支补强**
- From: PII 2.1-2.8 已有集成测试，但 chat pipeline 的 missing model、PII fail-closed、Upstream5xx/429/generic、response skip、usage 缺失等分支未完全覆盖。
- To: 补齐所有 gateway runtime/user/security 分支，保持明文 prompt/response/API key 不落库、不落日志、不进 fixture。
- Reason: 数据隔离网关是合规红线，测试必须覆盖失败姿态。
- Impact: 非破坏性；不改变外部 API 语义。

**基础设施与生命周期测试**
- From: `/healthz`、`/readyz`、`/v1/models`、lifespan、database lazy init、Redis pool、streaming helper、LLM Pydantic schema 缺少直接覆盖。
- To: 新增聚焦测试覆盖这些模块，外部 I/O 用 fake/mocking 边界替代真实 PG/Redis/LLM。
- Reason: 这些代码是 K8s HA、跨实例 trace、模型路由与可运维性的基础。
- Impact: 非破坏性；不新增部署依赖。

## Capabilities

### New Capabilities
- `audit-isolation-test-coverage`: 固化 audit-and-isolation 服务的 100% 真实测试覆盖、PII critical path、metadata-only audit 与失败降级门禁。

### Modified Capabilities
- `llm-egress-gateway`: 补充要求：本服务的 pytest-cov `app` coverage MUST 达到 100%，且 `verify.py` MUST 将覆盖率门禁纳入 release gate。
- `audit-and-isolation`: 补充要求：网关 PII 拦截、安全失败、readiness、credential/Redis/upstream 降级路径 MUST 由自动化测试覆盖。

## Impact

- 影响代码：`services/audit-and-isolation/tests/unit/`、`tests/integration/`、`verify.py`，以及少量 `app/*` 防御性不可达分支或真实 bug 修复。
- 影响 specs：新增 `audit-isolation-test-coverage` 质量能力 delta，并对 `llm-egress-gateway` / `audit-and-isolation` 增加测试门禁约束。
- 影响命令：`python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100` 成为必须通过的本服务门禁。
- Non-goals：不新增网关 API；不改变 6 类 PII 规则；不实现真实 K8s 双实例故障演练；不引入真实 LLM/credential/Redis/PostgreSQL 依赖；不做全局 unittest→pytest 重构。
- 源关联：`docs/architecture.md` §4 数据隔离网关与技术栈、`docs/prd.md` MVP 数据隔离/审计目标、GSTACK REVIEW REPORT eng-review #1/#9/#10/#11。