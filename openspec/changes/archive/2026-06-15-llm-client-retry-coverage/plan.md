# llm-client-retry-coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 补 `app/llm/client.py` 的 4 个 reachable missing 区域（`get_client` lazy init + `retry_with_redis` 2-iter loop + `_is_ha_failover` JSON parse + `reset_client_for_tests`）的 unit test,让 `client.py` 从 78% → 100% line coverage。0 行 source 改动（line 304/121 已是 `# pragma: no cover`）。

**Architecture:** ~11 个新 test 加到 `tests/unit/test_coverage_gaps_v1_followup.py`（与 `coverage-improvement` 同 file pattern,git history 清晰）。每个 test 走 2-5 minute TDD cycle（写 → 跑 → 验证 PASS）。单 commit + push + archive。

**Tech Stack:** pytest 8.x + pytest-cov 6.x + pytest-asyncio + respx（httpx mock）+ unittest.mock.AsyncMock。conda env `chatbiz`（CLAUDE.md 强制）。git。

**参考 artifacts**:
- `openspec/changes/llm-client-retry-coverage/{brainstorm,proposal,design}.md` — 已写
- `openspec/changes/llm-client-retry-coverage/specs/llm-client-coverage-100pct/spec.md` — 5 Requirements / 11 Scenarios
- `openspec/changes/llm-client-retry-coverage/tasks.md` — 5 个高阶 task
- `openspec/changes/coverage-improvement/{plan,retrospective}.md` — 模板参考

**产物路径说明**:本 plan 落在 openspec 强制路径 `openspec/changes/llm-client-retry-coverage/plan.md`。

---

## Task 1: Verify baseline (encoding prep)

**Files:** Verify-only.

- [ ] **Step 1.1: 跑 baseline cov 摸底**
```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
conda run -n chatbiz pytest tests/unit/test_coverage_gaps_v1_followup.py \
  tests/unit/test_retry.py --cov=app.llm.client --cov-report=term-missing --no-header 2>&1 | tail -10
```
Expected: `45 passed`,client.py `78%`,missing `74-80, 104-120, 214-215, 304, 334`。
Failure: 任何 FAILED → 基线已坏,**停止**。

- [ ] **Step 1.2: 验证 line 304/121 已是 `# pragma: no cover`**
```bash
grep -n "pragma: no cover" /Users/paulwang/work/ChatBiz/services/audit-and-isolation/app/llm/client.py
```
Expected: line 121 + line 304 都有 `# pragma: no cover`。
Failure: 缺任意一行 → source 已变,**停止**并 surface。

---

## Task 2: 补 get_client lazy init (line 74-80) 3 test

**Files:** Modify `services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`。

- [ ] **Step 2.1: 写 `test_get_client_initializes_httpx_async_client`**
参考 spec Scenario 1:mock `get_settings()` 返回 `upstream_timeout_ms=...`,调 `get_client()`,断言返回 `httpx.AsyncClient` 实例。先 `reset_client_for_tests()` 确保 `_client is None`。

- [ ] **Step 2.2: 跑 test 验证 PASS**
```bash
conda run -n chatbiz pytest tests/unit/test_coverage_gaps_v1_followup.py::test_get_client_initializes_httpx_async_client -v --no-cov 2>&1 | tail -3
```
Expected: `1 passed`。

- [ ] **Step 2.3: 写 `test_get_client_caches_returned_client`** (Scenario 2)
- [ ] **Step 2.4: 写 `test_get_client_uses_upstream_timeout_ms_setting`** (Scenario 3)
- [ ] **Step 2.5: 跑 get_client 部分 cov 验证 74-80 100%**

---

## Task 3: 补 retry_with_redis 2-iter loop (line 104-120) 4 test

**Files:** 同 test file。

- [ ] **Step 3.1-3.5**: 写 4 test,各走一个分支（5xx retry / connection interrupt / 两次 interrupt / 5xx+5xx），每写完立即跑。

参考 spec Scenario 4-7。**注意**:`asyncio.sleep` 需要 `monkeypatch.setattr` 或 `freezegun`,或直接 mock `asyncio.sleep` 不真等。

---

## Task 4: 补 _is_ha_failover JSON parse (line 214-215) 3 test

**Files:** 同 test file。

- [ ] **Step 4.1-4.3**: 写 3 test 各走一个分支（json raises → False / 503+HA body → True / 200 → False early return），每写完立即跑。

---

## Task 5: 补 reset_client_for_tests (line 334) 1 test

**Files:** 同 test file。

- [ ] **Step 5.1: 写 `test_reset_client_for_tests_clears_cache`**
- [ ] **Step 5.2: 跑验证 PASS**

---

## Task 6: 跑完整 cov 验证 100%

```bash
cd /Users/paulwang/work/ChatBiz/services/audit-and-isolation
conda run -n chatbiz pytest tests/unit/test_coverage_gaps_v1_followup.py \
  tests/unit/test_retry.py --cov=app.llm.client --cov-fail-under=100 --no-header 2>&1 | tail -10
```
Expected: `Required test coverage of 100% reached. Total coverage: 100.00%`,exit 0。
Failure: < 100% → 回到对应 Task 2-5 补 test。

- [ ] **Step 6.1: 跑 cov + verify**
- [ ] **Step 6.2: 验证既有 45 PASS 不被破坏**

---

## Task 7: 验证 production diff = 0

```bash
cd /Users/paulwang/work/ChatBiz
git diff --stat services/audit-and-isolation/app/llm/client.py
```
Expected: **空输出**。
Failure: 非空 → 意外改 prod code,立即回滚。

- [ ] **Step 7.1: 跑 prod diff 验证**

---

## Task 8: git add + commit

- [ ] **Step 8.1: git add test file**
- [ ] **Step 8.2: git commit with full message** (参考 tasks.md 4.2)
- [ ] **Step 8.3: 验证 commit 仅 test file 改动**

---

## Task 9: 写 verify.md + retrospective.md

参考 `coverage-improvement/verify.md` + `gateway-scanner-coverage-matrix/verify.md` 5-section 模板。

- [ ] **Step 9.1: 收集实际 command output** (cov 100% / prod diff 0 / commit)
- [ ] **Step 9.2: 写 verify.md**
- [ ] **Step 9.3: 写 retrospective.md** (5 section + NG1 NG2 still open)

---

## Task 10: openspec archive + git push

- [ ] **Step 10.1: sed tasks.md 全勾 [x]**
- [ ] **Step 10.2: yes y | openspec archive llm-client-retry-coverage**
- [ ] **Step 10.3: 验证 archive 落地 + spec 创建**
- [ ] **Step 10.4: git add archive + 新 spec + commit + push**

---

## Self-Review

**1. Spec coverage**:
- `get_client lazy init` → Task 2 (3 test)
- `retry_with_redis 2-iter` → Task 3 (4 test)
- `_is_ha_failover JSON parse` → Task 4 (3 test)
- `reset_client_for_tests` → Task 5 (1 test)
- 既有 45 PASS 不破坏 → Task 6.2
- 0 行 prod 改动 → Task 7

5 个 Requirement 全部有对应 Task。✓

**2. Placeholder scan**: 无 TBD / TODO / "should work"

**3. Type consistency**: `get_client` / `retry_with_redis` / `_is_ha_failover` / `reset_client_for_tests` 命名一致
