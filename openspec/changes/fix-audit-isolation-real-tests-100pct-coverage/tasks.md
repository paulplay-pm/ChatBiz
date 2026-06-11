## 1. Baseline 与测试骨架

- [ ] 1.1 在 `services/audit-and-isolation` 运行 pytest-cov baseline，保存 missing lines 清单到实现笔记
- [ ] 1.2 新增缺口驱动测试文件骨架：health/models/lifespan/database/redis/streaming/models_llm
- [ ] 1.3 验证测试骨架可被 pytest 收集且不会影响现有 127 个测试

## 2. API 与生命周期覆盖

- [ ] 2.1 为 `app/api/health.py` 补 `healthz` 与 `readyz` 全成功、PG fail、Redis fail、credential fail、routing empty 测试
- [ ] 2.2 验证 `/healthz` / `/readyz` 覆盖率达到 100%，且 readiness 失败返回 503
- [ ] 2.3 为 `app/api/models.py` 补 enabled-only、updated_at None、naive datetime、timezone-aware datetime 测试
- [ ] 2.4 验证 `/v1/models` 不暴露 upstream base_url/path/API key，覆盖率达到 100%
- [ ] 2.5 为 `app/main.py` lifespan 补 startup 成功、routing load 失败继续启动、shutdown stop/dispose 测试
- [ ] 2.6 验证 lifespan 测试不连接真实 PG/Redis/credential，且覆盖率达到 100%

## 3. 基础设施与 schema 覆盖

- [ ] 3.1 为 `app/database.py` 补 lazy engine、session factory、get_session 成功、get_session 异常、dispose 有/无 engine 测试
- [ ] 3.2 验证 database 测试不依赖真实 PostgreSQL，覆盖率达到 100%
- [ ] 3.3 为 `app/redis_client.py` 补 lazy pool、pool reuse、reset/dispose 测试
- [ ] 3.4 验证 Redis 测试不依赖真实 Redis，覆盖率达到 100%
- [ ] 3.5 为 `app/models/llm.py` 补 Message、ChatCompletionRequest、Choice、Usage、ChatCompletionResponse 默认值与字段约束测试
- [ ] 3.6 验证 LLM schema 覆盖率达到 100%

## 4. LLM、PII 与 audit 边界覆盖

- [ ] 4.1 为 `app/llm/streaming.py` 补 `reverse_stream` 空 chunk、非空 chunk、`buffer_and_reverse` 多 chunk 与空 stream 测试
- [ ] 4.2 验证 streaming helper 覆盖率达到 100%
- [ ] 4.3 扩展 PII redactor/reverser 测试：Redis set 失败、invalid JSON map、多 placeholder replace、无 PII 边界
- [ ] 4.4 扩展 PII rules 测试覆盖 Luhn/USCC helper 剩余分支
- [ ] 4.5 扩展 `AuditOutbox` 测试覆盖 start 幂等、task done restart、stop 正常/timeout、worker timeout continue、singleton reset
- [ ] 4.6 验证 PII 与 audit 测试无真实敏感信息，明文 prompt/API key 不落 fixture/log/audit

## 5. chat pipeline 错误分支覆盖

- [ ] 5.1 扩展 `test_api_chat.py` 覆盖 invalid header、missing model、message missing content、message non-string content
- [ ] 5.2 扩展 PII fail-closed 测试：`pii_fail_open=False` 时 redactor 异常返回 503
- [ ] 5.3 扩展 upstream 异常测试：`Upstream5xx`→502、`UpstreamRateLimited`→429、generic exception→502
- [ ] 5.4 扩展 response reverse skip 测试：choice 无 message、content 非 string、skip_pii=True 不 reverse
- [ ] 5.5 扩展 audit 字段测试：workflow_id、usage 缺失、token_input/token_output None、pii_types 去重语义
- [ ] 5.6 验证 chat pipeline 覆盖率达到 100%，且所有外部调用均为 fake/mock

## 6. 最小产品修复与不可达分支处理

- [ ] 6.1 根据 coverage report 定位 `credential_client.py`、`llm/client.py` 等不可达兜底行
- [ ] 6.2 优先重构真实可测试控制流；若不可合理重构，则添加 `# pragma: no cover` 并写明注释
- [ ] 6.3 验证所有产品代码改动均有对应测试或 verify.md 记录
- [ ] 6.4 执行安全校验：API key/private key grep、metadata-only audit、credential service 获取 key 路径不回退

## 7. verify.py 与最终验收

- [ ] 7.1 更新 `services/audit-and-isolation/verify.py`，将 pytest-cov 100% 作为首个 gate，并保留既有 18 项检查语义
- [ ] 7.2 运行 `PYTHONPATH=. python3 -m pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=100`
- [ ] 7.3 运行 `python3 verify.py`
- [ ] 7.4 单独运行 PII critical path 2.1-2.8，确认全部通过
- [ ] 7.5 写 `verify.md`：命令、退出码、测试数量、覆盖率表、产品修复/pragma 清单
- [ ] 7.6 写 `retrospective.md`：记录 coverage gotchas、异步测试 gotchas、后续 follow-up
