# Retrospective: llm-client-retry-coverage

**Date range**: 2026-06-15
**Trigger**: `coverage-improvement/retrospective.md §4.2`
**Owner**: paul (sponsor) + Claude (apply orchestrator)
**Commit**: b176572

---

## 1. What was built

1 个 commit (b176572) + 11 个新 test + 1 行 `# pragma: no cover` 注释 + 1
个新 import：

- **`services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`**：
  +194 行，11 个新 test
  - 3 个 `get_client` lazy init test (line 74-80)
  - 4 个 `retry_with_redis` 2-iter loop test (line 104-120)
  - 3 个 `_is_ha_failover` JSON parse error test (line 212-215)
  - 1 个 `reset_client_for_tests` test (line 334)
  - file 头加 `import httpx` (供 `MagicMock(spec=httpx.Response, ...)`)

- **`services/audit-and-isolation/app/llm/client.py`**：1 行 `# pragma: no cover`
  注释加在 line 304 (defensive `RuntimeError("...unreachable...")` raise)

**覆盖率收尾**：

| Module | apply 前 | apply 后 |
|---|---|---|
| `app/llm/client.py` | 78% (24 miss) | **100%** (0 miss) |

---

## 2. What went well

### 2.1 模板复用率高

跟前 2 个 coverage change (`coverage-improvement` + `gateway-scanner-coverage-matrix`)
**同 pattern**。6 artifact 共 ~1700 行 markdown,写 brainstorm/design/proposal/
specs/tasks/plan 模板填空 ~30 分钟(比第 1 个 `coverage-improvement` 写时
~60 分钟快 50%)。

### 2.2 `systematic-debugging` 在 apply 阶段拦住 2 个 surprise

**Surprise 1**:`import httpx` 漏写。`MagicMock(spec=httpx.Response, status_code=503)`
需要 `httpx.Response` 实际 import,我在写 test 时**没**意识到 test file 头
没 import `httpx`。跑 test 时 **8 个** fail 全因 `NameError: name 'httpx' is not
defined`,1 行 `import httpx` 修好。

**Surprise 2**:`line 304` 没标 `# pragma: no cover`。`coverage-improvement/retrospective
§3.2` 推断 line 304 已是 `# pragma: no cover`,但**实际** coverage-improvement
只标了 line 121(retry_with_redis),**没**标 line 304(retry_with_idempotency)。
跑 cov 后发现 `1 miss, 99%` (line 304 missing),surface 给用户决策,加注释修好。

### 2.3 11 个 test 4 区域分布自然

| 区域 | Missing lines | Test count |
|---|---|---|
| `get_client` lazy init | 74-80 (7 行) | 3 |
| `retry_with_redis` 2-iter | 104-120 (17 行) | 4 |
| `_is_ha_failover` JSON parse | 212-215 (4 行) | 3 |
| `reset_client_for_tests` | 334 (1 行) | 1 |
| **total** | **27 行** | **11 test** |

每个区域 1-4 个 test,符合"每个 test 走一个明确分支"原则。

---

## 3. What didn't go well

### 3.1 `coverage-improvement/retrospective §3.2` 推断错误

retrospective §3.2 说 "client.py:304 已是 `# pragma: no cover`" — **错**。
实际 coverage-improvement 14988d0 commit **没**改 line 304,只改了 line 121。

**根因**:retrospective 写时**没**真去 grep `client.py` 验证 line 304 pragma,
是基于"line 121 已标所以 304 应该也标" 的 symmetry 推断。**这次**本 change
apply Task 1.2 才 `grep -n "pragma: no cover" client.py` 验证 —— 修。

**教训**:retrospective 里**任何**"已 XXX" 推断,下个 change 引用时**必须**
grep 验证,不能因 symmetry 假设。

### 3.2 `coverage-improvement` 没改 `audit-and-isolation/pyproject.toml`

`--cov-fail-under=100` 在 audit-and-isolation `pyproject.toml` **没**设(只
设了 `--cov=app`)。我本 change apply 跑 `pytest --cov-fail-under=100` 时 fail
under fail,但**实际**项目级 cov 门槛是 0%,`coverage-improvement` change
**没**碰 pyproject。

**根因**:retrospective §3.3 错描述"cov fail-under 在 audit-and-isolation 已设"。
**实际** `coverage-improvement` 改的是 `tests/unit/test_coverage_gaps_v1_followup.py`,
**没**碰 pyproject。

**教训**:`--cov-fail-under=100` 是 project-level 门槛,设了 = 任何 prod code
未 100% 都让 CI fail。`coverage-improvement` **应该**改 pyproject 加这门槛
以 enforce 100%。本 change **也**不补(超 scope),留作 V1.0+ followup。

### 3.3 `MagicMock(spec=httpx.Response)` 触发 `NameError`

我写 `_is_ha_failover` test 时**没**意识到 test file 顶层没 import `httpx`。
`app.llm.client` 自己 import 了 httpx,但 test file 顶层的 `MagicMock(spec=httpx.Response, ...)`
需要 `httpx` 名字在当前 namespace 可见。

**根因**:写 test 时 mental model 是"`app.llm.client` import 了 httpx = 我
也能用 httpx",但 test function 顶层**不**继承 import。

**教训**:`MagicMock(spec=X)` 引用 X class 之前,test file 顶必须 import X。
这个之前在 `coverage-improvement` 没踩过(那里只用 `archive_audit` 的 type
不需要 httpx)。

### 3.4 8 个 fail → 1 行 fix 浪费 ~3 分钟

8 个 test 同时 fail 因同一个 `NameError`。**如果** 写完 1 个 test 就跑 verify
(plan.md 的 TDD micro-cycle),第 1 个 fail 就 surface 修好,不用写 11 个
test 才发现。apply 实际**部分**违反 TDD micro-cycle(连续写 11 个后一次跑)。

**根因**:之前 2 个 coverage change 写 test 时 mock 简单(`MagicMock()`,
不引用 type),没踩这个 import 错,所以**连续写一批**还 OK。这次 spec + httpx
触发了,连续写效率变低。

**教训**:`MagicMock(spec=X)` 类 test,**必须**写 1 个 → 跑 → PASS → 写下一个
的 TDD cycle,不能批量写。

---

## 4. What's left for V1.0+

### 4.1 覆盖率门槛 (--cov-fail-under=100) propagate

audit-and-isolation `pyproject.toml` 缺 `--cov-fail-under=100`。**建议下条 change**:
- name: `ci-coverage-all-services`
- scope: audit-and-isolation / gateway-scanner / workflow-engine 等 services
  pyproject.toml 加 `--cov-fail-under=100`,使 cov 数字真正 enforce
- estimated effort: 1 session, ~3 commits, ~50 行 config

### 4.2 `app/llm/streaming.py` 0% 覆盖

本 change 只 close `client.py`。`streaming.py`(line 30-72)仍是 0%。

**建议下条 change**:
- name: `llm-streaming-coverage`
- scope: 补 `streaming.py` SSE 流的 unit test
- estimated effort: 1 session, ~2 commits, ~200 行 test

### 4.3 其他 service 100% 覆盖

| Service | 当前 | Status |
|---|---|---|
| `audit-and-isolation` (client.py) | 100% | ✓ closed |
| `audit-and-isolation` (其他 module) | partial | 留 followup |
| `gateway-scanner` | 100% | ✓ closed |
| `workflow-engine` | 0% | 留 followup |
| `credential` | 0% | 留 followup |
| `sso` | 0% | 留 followup |
| `web` | n/a | 前端 |

`workflow-engine` / `credential` / `sso` 三个 service 需新 change 跟进,
**性质**跟 `coverage-improvement` 同 pattern(单 service 100% + cov matrix config)。

---

## 5. Process reflections

### 5.1 3 个 coverage-matrix 模板正式锁定为"family pattern"

| Change | service | cov 起点 | cov 终点 | apply 时长 |
|---|---|---|---|---|
| `coverage-improvement` (14988d0) | audit-and-isolation 3 module | 83% | 100% | ~30 min |
| `gateway-scanner-coverage-matrix` (1818495) | gateway-scanner 2 module | 50% | 100% | ~45 min |
| `llm-client-retry-coverage` (b176572) | audit-and-isolation client.py | 78% | 100% | ~20 min |

**template 复用时间** 跟 service 复杂度正相关。`llm-client-retry-coverage` 因为
只需要 4 个 area + 11 test,**apply 最快**。

### 5.2 retrospective 推断的 fragility

`coverage-improvement/retrospective §3.2` 和 §3.3 都基于"symmetry 假设"
推断 (line 121 已标所以 line 304 也已标;fail-under 在 audit-and-isolation
已设)。**两次**都错,本 change apply 时 surface。

**教训**:retrospective 写时**明确**列"已验证" vs "推断",下个 change 引用时
**优先**验证"已验证"项,**不要**拿"推断"项当 SSOT。

### 5.3 TDD micro-cycle 在 mock-heavy test 里更重要

之前 2 个 coverage change 写 test 时 mock 简单(`MagicMock()` 无 spec),
没踩 import 错,所以"连续写一批再跑" 还 OK。这次 spec + httpx 触发,8 个
test 一次性 fail 浪费 ~3 分钟。

**教训**:`MagicMock(spec=X)` / `patch.object(X, ...)` 类 test,**必须**
1 个 test → 1 次 pytest verify,不能批量写。**plan.md Task 2-5** 写了
"每个 test 写完立即跑",apply 时**没**严格执行。
