## Why

`openspec/changes/archive/2026-06-15-coverage-improvement/retrospective.md`
§4.2 提议的下一条 change：

> | `retry_with_idempotency` wrapper body (client.py:240-304) |
> | name: `llm-client-retry-coverage` |
> | scope: 补 `retry_with_idempotency` 的 3-attempt/5s 预算 /
> HA_FAILOVER 503 重试 / `last_exc` raise / `last_resp` return
> 4 个分支的 unit test |

紧接 `coverage-improvement` (commit 7fe8e91) + `gateway-scanner-coverage-matrix`
(commit 1818495) 后,`app/llm/client.py` 仍 78% line coverage (24 miss),
主要因 retry decorator body 错误路径 + `get_client` lazy init +
`_is_ha_failover` 错误路径未走测试。

**源参考**：
- 触发源：`coverage-improvement/retrospective.md §4.2`
- 模板：`coverage-improvement/` 6 artifact + `gateway-scanner-coverage-matrix/`
  6 artifact 完整 trace

## What Changes

**新增 capability：`llm-client-coverage-100pct`**

- From: `app/llm/client.py` 78% line coverage (24 miss)
- To: `app/llm/client.py` 100% line coverage (0 miss)
- Reason: 关闭 `coverage-improvement/retrospective.md §4.2`
- Impact: **non-breaking**。0 行 source 改动(line 304/121 已
  `# pragma: no cover`),仅追加 test

**新增 ~6-8 个 test 函数**（`tests/unit/test_coverage_gaps_v1_followup.py`
或新 `tests/unit/test_llm_client_coverage.py`,视 `coverage-improvement`
是否同 file pattern）

- From: client.py 24 miss(74-80 / 104-120 / 214-215 / 304 / 334)
- To: 0 miss
- Reason: 让 `compute_idempotency_key` 函数 100% 之外,整个 client.py
  100% line coverage
- Impact: **non-breaking**。test 新增是 additive

## Capabilities

### New Capabilities
- `llm-client-coverage-100pct`: 让
  `services/audit-and-isolation/app/llm/client.py` 通过 pytest 单元
  测试达到 100% line coverage。覆盖 `get_client` lazy init +
  `retry_with_redis` 2-iter loop + `_is_ha_failover` 错误路径 +
  `reset_client_for_tests` 入口。

### Modified Capabilities
无。本 change 不修改任何已存在 capability 的 REQUIREMENTS。

## Impact

**受影响的代码**：
- 新增跟踪：`services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`
  ~6-8 个新 test（与 `coverage-improvement` 同 file pattern）

**前端范围 / 后端范围 / 是否豁免前端**：
- 后端范围：是（`audit-and-isolation` 是 Python FastAPI service）
- 前端范围：否
- **豁免前端**：本 change 仅追加 Python 单元测试

**API / DB / 协议层影响**：无。本 change 是测试 followup，不修改
LLM upstream 调用、Idempotency-Key 生成、HA failover 语义。

**依赖**：无新增 PyPI 依赖。`pytest`、`pytest-asyncio`、
`unittest.mock`、`respx`(用于 httpx mock,如已有) 已在
`audit-and-isolation` dev 依赖中。

**CI 集成**：apply 完成后,新增 test 会自动被 `audit-and-isolation`
unit test 套件收集。CI workflow 改造留待 `ci-coverage-all-services`。

## Non-goals

- **NG1**：不补 `__main__.py` / `scanner.py` / `routing/table.py` 等
  其它文件 —— `coverage-improvement` 已关
- **NG2**：不加 CI workflow 改造 —— 留 `ci-coverage-all-services`
- **NG3**：不改 client.py 任何 production code —— 0 行 source 改动
- **NG4**：不重写 `retry_with_idempotency` / `_is_ha_failover` 的语义
- **NG5**：不测 `__import__("X")` AST 解析的 pattern 4 chain
  —— 那是 `gateway-scanner-coverage-matrix` 范围

## Future-Implementation 标注检查

本 change **不**触及 API/DB/前端契约，**不**适用
`[FUTURE-IMPLEMENTATION]` tag。

## eng-review 冲突检查

本 change **不**触及设计 doc "## GSTACK REVIEW REPORT" 中 12 个锁定
决策任一条。
