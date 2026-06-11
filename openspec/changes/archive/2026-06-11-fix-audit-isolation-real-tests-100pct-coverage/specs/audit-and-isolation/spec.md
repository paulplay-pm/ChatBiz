## ADDED Requirements

### Requirement: 可运维端点覆盖
数据隔离网关 MUST 对 `/healthz`、`/readyz` 和 `/v1/models` 提供自动化测试，覆盖成功与依赖失败路径，支撑 eng-review #1 的 HA 与健康检查要求。

#### Scenario: healthz liveness
- **WHEN** 测试调用 `GET /healthz`
- **THEN** 系统 MUST 返回 200 与 JSON `{"status":"ok"}`，且不访问 PostgreSQL、Redis 或 credential service

#### Scenario: readyz 全部依赖可用
- **WHEN** PostgreSQL、Redis、credential service 与内存 routing table 均可用
- **THEN** `GET /readyz` MUST 返回 200，并在 checks 中标记 `postgres`、`redis`、`credential_service`、`routing_table` 为 `ok`

#### Scenario: readyz 任一依赖失败
- **WHEN** PostgreSQL、Redis、credential service 任一检查抛异常或 routing table 为空
- **THEN** `GET /readyz` MUST 返回 503，并在 JSON body 中标出失败依赖

#### Scenario: models 只返回启用路由
- **WHEN** `model_routing` 表包含 enabled 与 disabled 模型
- **THEN** `GET /v1/models` MUST 只返回 enabled 模型，且 MUST NOT 暴露 upstream base_url/path/API key

### Requirement: 生命周期与基础设施封装覆盖
数据隔离网关 MUST 对 FastAPI lifespan、SQLAlchemy lazy engine/session、Redis pool factory 与 dispose/reset 路径提供自动化测试。

#### Scenario: lifespan startup/shutdown
- **WHEN** FastAPI lifespan 启动并关闭
- **THEN** 系统 MUST 尝试加载 routing table，MUST 启动 audit outbox，关闭时 MUST stop outbox 并 dispose SQLAlchemy engine

#### Scenario: routing load 失败仍启动
- **WHEN** startup 阶段 routing table load 抛异常
- **THEN** lifespan MUST 记录 warning 并继续启动，后续请求通过空路由表失败而不是进程崩溃

#### Scenario: database session 成功与异常
- **WHEN** `get_session()` 正常 yield 或内部抛异常
- **THEN** 测试 MUST 验证 session factory lazy init、正常关闭、异常传播与 dispose 行为

#### Scenario: Redis pool 复用
- **WHEN** 多次调用 `get_redis()`
- **THEN** Redis connection pool MUST lazy 初始化并复用；测试 MUST 覆盖 reset/dispose 类测试辅助路径

### Requirement: LLM schema 与 streaming helper 覆盖
数据隔离网关 MUST 对 OpenAI-shaped Pydantic models 与 streaming reverse helper 提供自动化测试，确保 SDK 兼容路径不因未覆盖而回退。

#### Scenario: LLM request/response schema
- **WHEN** 测试构造 chat completion request、message、choice、usage 与 response
- **THEN** Pydantic schema MUST 验证默认值、字段约束、role/content 类型与 token usage 字段

#### Scenario: streaming reverse
- **WHEN** 上游 streaming chunks 含占位符或空 chunk
- **THEN** streaming helper MUST 对非空 chunk 调用 reverse 并 yield，MUST 跳过或正确处理空 chunk

#### Scenario: buffer and reverse
- **WHEN** 上游 async iterator 返回多个 chunks
- **THEN** buffer helper MUST 拼接完整文本并按 trace_id 做一次 reverse，还原后的字符串 MUST 返回给调用方

### Requirement: 产品修复与 pragma 透明记录
本 change 中任何产品代码修复或 `# pragma: no cover` MUST 在 `verify.md` 中逐项记录，说明触发测试、变更原因、风险与后续计划。

#### Scenario: 产品代码修复记录
- **WHEN** 实现改动 `app/**/*.py`
- **THEN** `verify.md` MUST 列出文件、变更摘要、关联测试与是否改变外部行为

#### Scenario: pragma 记录
- **WHEN** 实现新增 `# pragma: no cover`
- **THEN** `verify.md` MUST 说明该分支为什么真实控制流不可达，以及为什么不使用 artificial test
