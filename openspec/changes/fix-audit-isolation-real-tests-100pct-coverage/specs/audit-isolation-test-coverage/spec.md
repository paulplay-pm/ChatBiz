## ADDED Requirements

### Requirement: audit-and-isolation 单元覆盖率门禁
`services/audit-and-isolation` MUST 以 pytest-cov 对 `app` 包执行单元/集成测试，并且总覆盖率 MUST 达到 100%。覆盖率门禁 MUST 作为 release gate；任何 missing line MUST 阻断本服务发布。

#### Scenario: pytest-cov 100% 通过
- **WHEN** 开发者在 `services/audit-and-isolation` 执行 `PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100`
- **THEN** 测试 MUST 全部通过，coverage TOTAL MUST 为 100%，命令 MUST 以 exit code 0 结束

#### Scenario: 任一 app 行未覆盖
- **WHEN** pytest-cov 报告任一 `app/**/*.py` 行 missing
- **THEN** 命令 MUST 失败，且开发者 MUST 先补真实测试或记录不可达 pragma 后才允许 release

### Requirement: verify.py 覆盖率聚合门禁
`services/audit-and-isolation/verify.py` MUST 显式执行 pytest-cov 100% 覆盖率门禁，并保留既有安全、OpenAPI、docker-compose、PII 规则、outbox、lifespan 等静态/动态检查。

#### Scenario: verify.py 作为 CI gate
- **WHEN** 开发者在 `services/audit-and-isolation` 执行 `python3 verify.py`
- **THEN** verify MUST 运行覆盖率门禁，MUST 保留安全 grep 与现有 18 项检查语义，全部通过后 MUST 返回 exit code 0

#### Scenario: 覆盖率不足
- **WHEN** pytest-cov 覆盖率低于 100%
- **THEN** `verify.py` MUST 返回非 0 exit code，并在输出中标记 coverage gate 失败

### Requirement: 真实测试优先
测试 MUST 覆盖产品真实行为与公开函数/API 语义；外部系统边界 MAY 使用 fake、respx 或 monkeypatch，但 MUST NOT 通过构造不可能控制流来只追求覆盖率。

#### Scenario: 外部边界 mock
- **WHEN** 测试需要覆盖 credential service、upstream LLM、Redis 或 PostgreSQL 依赖
- **THEN** 测试 MUST 使用 fake/respx/monkeypatch 替代真实外部服务，且断言调用方可观察行为

#### Scenario: 不可达防御分支
- **WHEN** 覆盖率缺口来自真实控制流不可达的防御性兜底
- **THEN** 实现 MUST 优先重构为可测试结构；若重构会降低可读性，MUST 使用 `# pragma: no cover` 并在 `verify.md` 记录文件、行与理由

### Requirement: PII critical path 2.1-2.8 不回退
本服务 MUST 保持 eng-review #11 锁定的 critical path #2“数据隔离网关 PII 拦截”8 个子场景自动化测试全部通过。

#### Scenario: PII critical path 子场景全量执行
- **WHEN** 执行 `python3 -m pytest tests/integration/test_pii_subscenario_2_*.py -v`
- **THEN** 身份证、手机/银行卡边界、邮箱/信用代码/营收、响应侧还原、Fail-Open、upstream timeout、credential down、trace 跨实例 8 个子场景 MUST 全部通过

### Requirement: 敏感信息安全测试全覆盖
测试与实现 MUST 保证 LLM provider API Key、主密钥、明文 prompt/response 不进入源码、测试 fixture、日志或 audit_log。

#### Scenario: API Key 不在源码或测试
- **WHEN** 安全检查扫描 `app/` 与 `tests/`
- **THEN** 检查 MUST NOT 发现硬编码的真实 API Key 或 private key

#### Scenario: 明文 prompt 不进入 audit_log
- **WHEN** 网关处理含假身份证、手机号、邮箱或金额的 prompt
- **THEN** audit_log 测试 MUST 验证只保存 metadata/hash/PII 类型与计数，MUST NOT 保存明文 prompt 或 response
