# llm-client-coverage-100pct Specification

## Purpose
TBD - created by archiving change llm-client-retry-coverage. Update Purpose after archive.
## Requirements
### Requirement: get_client lazy init 100% 单元测试覆盖 (MUST)
(MUST) 模块 `app/llm/client.py` 的 `get_client()` lazy init
路径(line 74-80)MUST 拥有可执行的 pytest 单元测试，
使该函数达到 100% line coverage。

#### Scenario: `get_client()` 第一次调用时初始化 `httpx.AsyncClient`
- **WHEN** 第一次调 `get_client()`(`_client` is None)
- **THEN** MUST 创建 `httpx.AsyncClient(timeout=..., limits=...)`
  基于 `get_settings().upstream_timeout_ms`
- **AND** 返回的 client MUST 是 `httpx.AsyncClient` 实例

#### Scenario: `get_client()` 第二次调用复用 cached client
- **WHEN** 第二次调 `get_client()`(`_client` is not None)
- **THEN** MUST 返回同一个 cached `_client`(不重新 init)

#### Scenario: `get_client()` init 配置使用 `upstream_timeout_ms` settings
- **WHEN** mock `get_settings()` 返回 `upstream_timeout_ms=5000`
- **AND** 第一次调 `get_client()`
- **THEN** 创建的 `httpx.AsyncClient` 的 `timeout` MUST 等于 5.0 秒
  （即 `5000 / 1000`）

### Requirement: retry_with_redis 2-iter loop 100% 单元测试覆盖 (MUST)
(MUST) 装饰器 `retry_with_redis`(line 95-121, 实现在
`call_upstream` 函数)MUST 拥有可执行的 pytest 单元测试，覆盖
2-iteration 重试循环的 3 个分支:5xx retry / connection-interrupted
exception / last iteration return-or-raise。

#### Scenario: 5xx 响应在 attempt 0 时 retry, attempt 1 时 return
- **WHEN** mock upstream 返回 `resp.status_code=500` (attempt 0)
- **THEN** MUST `asyncio.sleep(0.2)` 后 retry
- **AND** 第二次调用 mock upstream 返回 `resp.status_code=200` (attempt 1)
- **THEN** MUST return 该 200 resp

#### Scenario: connection-interrupted exception 在 attempt 0 时 retry
- **WHEN** 第一次调 upstream raises `httpx.TimeoutException` (attempt 0)
- **THEN** MUST `asyncio.sleep(0.2)` 后 retry
- **AND** 第二次调 upstream 返回 200 (attempt 1)
- **THEN** MUST return 200 resp

#### Scenario: 两次 connection-interrupted exception 全部 raise
- **WHEN** 两次调 upstream 都 raise `httpx.TimeoutException`
- **THEN** MUST raise `httpx.TimeoutException` (last_exc)

#### Scenario: 第一次 5xx + 第二次 5xx 仍 retry then raise
- **WHEN** 两次调 upstream 都返回 `resp.status_code=500`
- **THEN** MUST `asyncio.sleep(0.2)` 一次 (attempt 0 → attempt 1)
- **AND** attempt 1 MUST 直接 return resp(因 `attempt == 0` 为 False
  不 retry)

### Requirement: _is_ha_failover JSON parse 错误路径 100% 覆盖 (MUST)
(MUST) 函数 `_is_ha_failover(resp)`(line 209-216)对 `resp.json()`
抛异常的 fallback 路径(line 212-215)MUST 拥有可执行的 pytest
单元测试。

#### Scenario: `_is_ha_failover` 在 `resp.json()` 抛异常时返回 False
- **WHEN** mock `httpx.Response` 的 `resp.json` side_effect 为
  `ValueError("not JSON")`
- **THEN** MUST 返回 `False`(fallback to non-HA detection)

#### Scenario: `_is_ha_failover` 在 503 + valid HA body 时返回 True
- **WHEN** mock `resp.status_code == 503` + `resp.json()` 返回
  `{"error": "HA_FAILOVER"}`
- **THEN** MUST 返回 `True`

#### Scenario: `_is_ha_failover` 在 200 时返回 False
- **WHEN** mock `resp.status_code == 200`
- **THEN** MUST 返回 `False`(line 210-211 early return,不走 JSON parse)

### Requirement: reset_client_for_tests 100% 单元测试覆盖 (MUST)
(MUST) 函数 `reset_client_for_tests()`(line 331-334)MUST 拥有
可执行的 pytest 单元测试，使该函数达到 100% line coverage。

#### Scenario: `reset_client_for_tests` 清空 cached client
- **WHEN** 第一次调 `get_client()`(设 `_client` 为某个 `httpx.AsyncClient`)
- **AND** 调 `reset_client_for_tests()`
- **THEN** module-level `_client` MUST 重置为 `None`
- **AND** 下次 `get_client()` MUST 重新 init

### Requirement: 既有 45 PASS 不被破坏 (MUST)
(MUST) 现有 23 个 test 在 `tests/unit/test_retry.py` + 22 个 test 在
`tests/unit/test_coverage_gaps_v1_followup.py` MUST 保持 PASS 状态
不被新 test 破坏。

#### Scenario: 既有 45 PASS 状态保持
- **WHEN** 在 `services/audit-and-isolation/` 目录下运行
  `pytest tests/unit/test_retry.py tests/unit/test_coverage_gaps_v1_followup.py
  --no-cov`
- **THEN** 既有 45 个 test MUST PASS
- **AND** MUST 不出现 FAILED 或 ERROR

### Requirement: 既有 production code 契约不变 (MUST)
(MUST) 本 change MUST 不修改 `app/llm/client.py` 任何 production
code；本 change 是纯测试 followup，0 行 source 改动。

#### Scenario: client.py prod diff = 0
- **WHEN** 本 change apply 完成，`git diff HEAD~<N> HEAD --stat
  services/audit-and-isolation/app/llm/client.py`
- **THEN** 输出 MUST 为空（diff 为零字节）

