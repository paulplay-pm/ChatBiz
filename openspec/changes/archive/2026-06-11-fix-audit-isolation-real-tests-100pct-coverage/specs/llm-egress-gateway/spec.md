## MODIFIED Requirements

### Requirement: 4 critical path 100% 覆盖(eng-review Test #2)
本服务 = 4 critical path 中的 #2 "数据隔离网关 PII 拦截"。测试 MUST 100% 覆盖 8 个子场景，并且 `services/audit-and-isolation` 的 pytest-cov `app` 覆盖率 MUST 达到 100%。coverage gate 与 critical path gate 任一失败 MUST 阻断 release。

#### Scenario: PII 拦截子场景 2.1 — 身份证脱敏 + 还原
- **WHEN** e2e 测试:调用方发含身份证的 prompt → 假 LLM 返回含占位符的 response
- **THEN** 测试 MUST 验证:① 脱敏后 prompt 不含原身份证 ② response 还原后含原身份证 ③ audit_log 记 pii_detected_types=["id_card"]

#### Scenario: PII 拦截子场景 2.2 — 手机/银行卡边界
- **WHEN** 测试发"010-12345"(5 位业务号)+ 真实手机号 13800138000
- **THEN** 测试 MUST 验证:① 业务号未命中 ② 手机号被脱敏

#### Scenario: PII 拦截子场景 2.3 — 邮箱/信用代码/营收
- **WHEN** 测试发邮箱 + 18 位统一社会信用代码 + "营收 1,234,567.89 元"
- **THEN** 测试 MUST 验证:3 类全部脱敏

#### Scenario: PII 拦截子场景 2.4 — 响应侧还原
- **WHEN** 同 trace 2 次 LLM 调用,response 都含占位符
- **THEN** 测试 MUST 验证:2 次都还原为同一原值

#### Scenario: PII 拦截子场景 2.5 — Fail-Open
- **WHEN** PII detector 抛异常(monkey-patch)
- **THEN** 测试 MUST 验证:① 请求 200(不阻断)② 原文本到上游 ③ audit 记 PIIDetectorUnavailable

#### Scenario: PII 拦截子场景 2.6 — 上游 timeout
- **WHEN** 假 LLM mock 30s+ 不响应
- **THEN** 测试 MUST 验证:① 返 504 ② audit 记 UpstreamTimeout

#### Scenario: PII 拦截子场景 2.7 — credential down
- **WHEN** credential service mock 不可达
- **THEN** 测试 MUST 验证:① 返 503 ② audit 记 CredentialServiceUnavailable

#### Scenario: PII 拦截子场景 2.8 — trace 跨实例
- **WHEN** 实例 A 处理后 Redis 写入 map,实例 B 收到同 trace 后续请求
- **THEN** 测试 MUST 验证:实例 B 能从 Redis 拉 map 还原

#### Scenario: audit-and-isolation app 覆盖率 100%
- **WHEN** 执行 `PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100`
- **THEN** 本服务 app 包覆盖率 MUST 为 100%，且命令 MUST 以 exit code 0 结束

## ADDED Requirements

### Requirement: 网关错误分支覆盖
OpenAI-compatible 代理端点 MUST 由自动化测试覆盖 user、runtime、security 三类错误边界；canvas drag-loop 在本服务 N/A，但 MUST 在文档中说明不适用。

#### Scenario: user 错误覆盖
- **WHEN** 请求缺少 model、缺少 X-Trace-Id、缺少 X-Model-Kind、JSON 非法或 body 超过 1MB
- **THEN** 测试 MUST 验证网关返回对应 422/413/400 响应，且不会调用上游 LLM

#### Scenario: runtime 错误覆盖
- **WHEN** credential service 不可达、upstream LLM 返回 5xx、timeout、429 或未知异常
- **THEN** 测试 MUST 验证网关返回 503/502/504/429，且相应 metric/audit 语义不回退

#### Scenario: security 错误覆盖
- **WHEN** 请求缺少 Authorization、token 非 Bearer 或 credential auth verify 失败
- **THEN** 测试 MUST 验证网关 fail-closed 返回 401，且不继续处理 PII 或上游调用
