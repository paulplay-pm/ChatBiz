# Retrospective — fix-audit-isolation-real-tests-100pct-coverage

## What went well

- 200 tests 全量通过，`app` 100% coverage — 从启动到完结用了不到 1 天。
- 新增 7 个测试文件 + 扩展 3 个，全部覆盖真实行为路径，不依赖真实 PG/Redis/LLM。
- 与 `workflow-engine` 100% coverage follow-up 的教训保持一致：小产品修复 + pragma 明确记录、不写 artificial monkeypatch 测试不可达路径。
- `verify.py` 扩展为 pytest-cov gate，保留所有现有安全检查。

## Gotchas

### fakeredis 全局拦截 monkeypatch
`test_redis_client.py` 的 monkeypatch 被 fakeredis 全局拦截，导致 `get_redis()` 实际返回 FakeRedis 而非 mock。解决方案：主动 reload `_pool` 并还原真实 `get_redis` 引用；跨模块污染通过 fixture 在前后都 reset。

### Pyright 对测试文件中的 monkeypatch 重复报 `unknown attribute`
`reportAttributeAccessIssue` 是 Pyright 对动态 monkeypatch 的误报，运行时全部正常。采用同 `workflow-engine` 的策略：优先级 `✘` error 修复，`★` info 级别接受。

### `verify.py` unittest discover 混 pytest 测试
pytest-asyncio 和 unittest 混跑没有问题，但 `verify.py` 第 1 gate 已改 pytest-cov，2/3 仍用 unittest discover 保留既有运行习惯。

### whitelist-generic-exception 难以完全消除
Pyright 诊断中 `credential_client.py`、`client.py` 出现 `reportAttributeAccessIssue` 因为 `get_settings()` 返回 frozen `Settings` 实例未在其类型声明中列出某些字段。这些不是代码缺陷，不影响运行时，本 change 不做 Settings model 改动。

## Decisions confirmed

- D1（真实测试优先 + 最小产品修复/pragma）：确认。所有 pragma 均 audit-writer/chat pipeline/redis-client/API 真实输入覆盖后剩余不可达路径。
- D2（pytest-cov 主门禁 + verify.py 聚合）：确认。`verify.py` 第 1 gate 改为 pytest-cov 100% 覆盖扫描，其余安全检查不变。
- D4（外部依赖只在边界 fake/mock）：确认。所有新增测试均未创建真实连接。

## Follow-ups

1. `test_api_chat.py` 的 `test_body_too_large_413` 在 `orjson.loads` 之前先做 `len(body_bytes)` 判断，因为 orjson 对超大 body 处理成本高。该测试当前通过 1.2MB body 验证 413 返回正确。
2. 现有 3 个 `AsyncMock` warning（`test_audit_writer.py`）不是本轮新增；这些测试 runner 在 unittest 中同步运行异步 `s.add(rec)` 导致的。后续可用 `pytest-asyncio` 改写消除。
3. `README.md` 列出 `POST /v1/completions` 但当前路由不含该端点；这是文档漂移，不在本 change 里修。
4. 可考虑后续增加一个 docker-compose smoke test 验证真实 HA readiness 行为。
