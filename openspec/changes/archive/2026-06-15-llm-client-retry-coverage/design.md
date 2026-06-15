## Context

`coverage-improvement/retrospective.md §4.2` 提议的下一条 change：
补 `app/llm/client.py` 的 retry decorator body + `get_client` lazy
init + `_is_ha_failover` 错误路径 unit test。

**当前状态**（apply 阶段跑 cov 摸底）：
- `app/llm/client.py`：108 stmts, 24 miss, **78%**
- Missing 行: **74-80** / **104-120** / **214-215** / **304** / **334**
- 现有 23 PASS in `tests/unit/test_retry.py` + 22 新 PASS in
  `tests/unit/test_coverage_gaps_v1_followup.py` = 45 个 test PASS
- `__init__.py` 0 stmts 100% covered,其余 0% 因其他 test file 未跑

**约束**：
- 0 行 production code 修改（line 304/121 已是 `# pragma: no cover`）
- 不引入新 PyPI 依赖
- 不动 12 个 eng-review 决策任一条
- 不触及 API/前端契约

**利益相关方**：
- paul（C-level sponsor，retrospective 验收方）
- `audit-and-isolation` service owner（CI / 维护者）
- 跟 `coverage-improvement` + `gateway-scanner-coverage-matrix` 同 pattern 复用

## Goals / Non-Goals

**Goals:**

- **G1**：`app/llm/client.py` 从 78% 提升到 **100%** line coverage
  （pytest-cov 数字，4 个 reachable missing 区域走完：74-80 /
  104-120 / 214-215 / 334）
- **G2**：0 行 source 改动（line 304/121 已是 `# pragma: no cover`）
- **G3**：既有 45 PASS 不被破坏（23 retry + 22 coverage_gaps_v1_followup）

**Non-Goals:**

- **NG1**：不补 `__main__.py` / `scanner.py` / `routing/table.py` —— 
  `coverage-improvement` 已关
- **NG2**：不加 CI workflow —— 留 `ci-coverage-all-services`
- **NG3**：不改 `client.py` 任何 production code
- **NG4**：不重写 retry decorator 语义
- **NG5**：不重命名现有 test file —— 沿用
  `test_coverage_gaps_v1_followup.py` 同 file pattern（与
  `coverage-improvement` 一致）

## Decisions

### D1：change name = `llm-client-retry-coverage`

- **选择**：`llm-client-retry-coverage`
- **理由**：
  - 与 retrospective §4.2 引用链 1:1
  - "retry-coverage" 暗示 retry decorator 是重点,但实际 missing 包含
    `get_client` + `_is_ha_failover` 错误路径
- **已考虑 alternative**：
  - `client-py-100pct-line-cov`（B）：太泛，未来其他 client.py 改动
    会被错误归到这里
  - `retry-decorator-coverage`（C）：scope 缩太窄，缺 `get_client` 等

### D2：scope = 补 ~6-8 个 test 让 client.py 24 miss 走完

- **选择**：4 个 reachable missing 区域各 1-3 个 test，共 ~6-8 个
- **理由**：
  - retrospective §4.2 明确 narrow scope
  - 跟 `coverage-improvement` 同 pattern(纯 test followup)
- **已考虑 alternative**：
  - B：扩到全 audit-and-isolation 100% —— `coverage-improvement` 已关
  - C：加 CI workflow —— `ci-coverage-all-services` 范围

### D3：测 `get_client()` lazy init (line 74-80)

- **选择**：1 个 test，先 `reset_client_for_tests()` 删缓存 + mock
  `get_settings()` 返回 `upstream_timeout_ms=...` + 调 `get_client()`
- **理由**：
  - 7 行 missing 是真 reachable
  - 现有 `test_retry.py` 已有 `reset_client_for_tests()` pattern

### D4：测 `retry_with_redis` body (line 104-120) 3 个分支

- **选择**：3 个 test,各走一个分支
  - 5xx retry：`resp.status_code >= 500 and attempt == 0` → sleep → continue
  - Connection interrupt：`TimeoutException / RemoteProtocolError` → sleep → continue
  - Last iteration：直接 return resp 或 raise last_exc
- **理由**：
  - 17 missing 拆 3 个 test 干净
  - 现有 `test_retry.py` 已有 mock `httpx.AsyncClient` + `asyncio.sleep` pattern

### D5：测 `_is_ha_failover` 错误路径 (line 214-215)

- **选择**：1 个 test,mock `httpx.Response`,`resp.json.side_effect = ValueError(...)`
- **理由**：
  - 2 missing 是 `except Exception: return False` 分支
  - 单 test 走完

### D6：0 行 source 改动

- **选择**：line 304/121 已 `# pragma: no cover`,本 change 不标新
- **理由**：
  - 跟 `coverage-improvement` §3.2 同 pattern
  - 跑 cov 后如果发现**新** unreachable branch,再 surface 给用户

### D7：走完整 openspec 8 artifact 流程

- **选择**：brainstorm → proposal → design → specs → tasks → plan
  → apply → verify → retrospective
- **理由**：跟前 2 个 coverage change 同 pattern

### D8：跳过本地 design doc 走 openspec

- **选择**：只写 `openspec/changes/llm-client-retry-coverage/brainstorm.md`
- **理由**：前 2 个 change 用户显式选 A
- **已考虑 alternative**：双写 openspec + 本地 design doc —— 浪费

## Risks / Trade-offs

- **[Risk] R1**：`retry_with_redis` body 测需要 mock `httpx.AsyncClient` +
  `asyncio.sleep`,可借鉴 `test_retry.py` 已有 pattern
  → Mitigation：先 grep `test_retry.py` 找 mock pattern 复用

- **[Risk] R2**：`get_client()` lazy init 测需要先
  `reset_client_for_tests()`,但 module-level `_client` 是 global state
  → Mitigation：用 fixture 隔离(autouse 每个 test 前 reset)

- **[Risk] R3**：跑 cov 后可能发现**新** unreachable branch(比如 mock
  行为不真)需要 surface 给用户决策
  → Mitigation：apply 阶段 cov 数字差异 surface via AskUserQuestion

- **[Trade-off] T1**：保留 `_is_ha_failover` 1 个 test 而非拆 2-3 个 →
  接受理由:1 个 mock setup 走 2 missing 行(test/except),比例合理

- **[Trade-off] T2**：用 `test_coverage_gaps_v1_followup.py` 同 file 而非
  新 `test_llm_client_coverage.py` → 接受理由:跟 `coverage-improvement`
  同 pattern,git history 清晰

## Migration Plan

N/A — 本 change **不**涉及部署变更。

**具体说明**：
- 不修改 `app/llm/client.py` 任何 production code
- 不修改任何 endpoint、retry decorator 行为、Idempotency-Key 生成语义
- 不引入新 PyPI 依赖
- 不动 `services/audit-and-isolation/` 之外任何 service

**部署顺序**（apply 阶段）：
1. 跑 baseline cov 摸底 (Task 1)
2. 补 6-8 个 test (Task 4-5)
3. 单 commit (Task 6)
4. openspec archive (Task 7)

**回滚策略**：
- 纯 test followup，回滚 = `git revert <commit>`
- 无生产影响

**验收条件**：
- `pytest tests/unit/test_coverage_gaps_v1_followup.py
  tests/unit/test_retry.py --cov=app.llm.client --cov-fail-under=100` →
  全 PASS，2 module 100% covered，exit 0
- `git diff services/audit-and-isolation/app/llm/client.py` 输出为空

## Open Questions

**无**。
