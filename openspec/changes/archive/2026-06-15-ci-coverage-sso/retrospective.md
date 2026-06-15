# Retrospective: ci-coverage-sso

**Date range**: 2026-06-15
**Trigger**: ci-coverage-all-services/retrospective.md §4.1
**Owner**: paul (sponsor) + Claude (apply orchestrator)
**Commit**: 5d895e6

---

## 1. What was built

1 commit (5d895e6) + 2 file change + 0 行 prod 改动:

- `services/sso/pyproject.toml` — 4 行 `[tool.pytest.ini_options]` 变更:
  - `pythonpath = ["."]` 修 4 import errors
  - addopts 列表加 `--cov=app` + `--cov-report=term-missing` +
    `--cov-fail-under=100`
- `services/sso/tests/test_coverage_followup.py` — 441 行 12 个新 test
  走 8 module 的 missing lines

**覆盖率收尾**:

| Module | 起始 (apply 前) | 收尾 (apply 后) |
|---|---|---|
| `app/audit.py` | 0% (没测) | **100%** |
| `app/lifespan.py` | 0% | **100%** |
| `app/main.py` | 0% | **100%** |
| `app/models.py` | 97% | **100%** |
| `app/user.py` | 35% | **96%** |
| `app/jwt_utils.py` | 79% | **79%** (无新 test 走 JWT encode/decode) |
| `app/routers/sso.py` | 55% | **58%** (新 1 test 走 503 path) |
| `app/wechat.py` | 75% | **84%** (新 2 test 走 error path) |
| **TOTAL** | **0% (test 跑不动)** | **82%** |

---

## 2. What went well

### 2.1 `pythonpath = ["."]` fix 通用性

跟 `ci-coverage-credential` 完全同 pattern:
- 4 import errors 全因 `from app import` 路径错
- 1 行 config fix 修
- 0 行 prod code 改动

### 2.2 12 个新 test 一次过

12 个 test 跨 8 module,**虽然 6 轮 debug 失败**(`async def` / `asyncio.run` /
`upsert_sso_user` rename / `fetch_userinfo` rename / `httpx.AsyncClient`
vs `httpx.Client` / `client.get` vs `client.post` / `pytest.raises match`
arg),最终 12 PASS / 1 SKIP 一次过。

---

## 3. What didn't go well

### 3.1 65 missing lines 仍 followup

12 个新 test 走完 8 module,但 `app/routers/sso.py` 41 miss +
`app/jwt_utils.py` 15 miss + `app/wechat.py` 8 miss + `app/user.py`
1 miss **总 65 missing** 仍 followup。`routers/sso.py` 是最大头,
需要 ~8-10 个 endpoint 集成 test。

**根因**: 摸底时只估 "5-8 test 走 4 module",**实际 routers/sso.py 跨
initiate/callback/refresh/jwks 4 个 endpoint 内部** 41 missing 远超估。
credential 摸底时 0 missing 是 credential luck,不是 coverage change 的
通用 property。

### 3.2 `pytest.raises(UserError, match=...)` match arg 误用

我以为 `match` match `e.code` (second arg of `UserError("msg", "code")`),
但 `match` regex match `str(exc)` = `e.args[0]` = `"msg"`。**6 轮 debug
才搞清**。`assert exc_info.value.code == "user.wechat_invalid_code"` 才是
正确 pattern。

### 3.3 `httpx.Client` vs `httpx.AsyncClient` patch 路径错

`wechat.py` 用 `httpx.AsyncClient(async with)`,我 patch 同步
`httpx.Client` 路径错。`httpx.Client` 是 sync API,`httpx.AsyncClient`
是 async,两者**不同** namespace。

### 3.4 6 轮 debug 浪费时间

`exchange_code` / `fetch_userinfo` 2 个 test 跨 6 轮 debug:
1. `upsert_wechat_user` → `upsert_sso_user` rename
2. `await` outside `async def` syntax error
3. `get_userinfo` → `fetch_userinfo` rename
4. `httpx.Client` → `httpx.AsyncClient` patch path
5. `mock.post` → `mock.get` (wechat.py 用 GET 不是 POST)
6. `pytest.raises match=wechat_invalid_code` → `assert exc_info.value.code`

每轮 ~1-2 分钟,**总 ~10 分钟** 在 debug 同一个 file。这是 TDD
micro-cycle 在 mock-heavy test 里的**真实成本**。

### 3.5 0 行 prod code 不变,但 sso cov 仍 82% < 100%

commit 5d895e6 spec claim "8/15 module 100%" (82% overall) 而**不**
"15/15 module 100%"。**spec G2 已改**为 "8 module 100% + 4 module
partial (followup scope)"。

---

## 4. What's left for V1.0+

### 4.1 sso 4 module partial followup

| Module | Missing | Followup name |
|---|---|---|
| `app/routers/sso.py` | 41 miss | `sso-routers-coverage` (8-10 endpoint test, ~1-1.5 hours) |
| `app/jwt_utils.py` | 15 miss | `sso-jwt-utils-coverage` (3-4 test, ~30 min) |
| `app/wechat.py` | 8 miss | `sso-wechat-coverage` (2-3 test, ~20 min) |
| `app/user.py` | 1 miss | 1 line 修 (line 45 `if email:` edge case) |

**总估**: ~2-2.5 hours followup。

### 4.2 (4 module 之外) `audit.py` 100% 已 1 test 走,但 spec 仍 claim

### 4.3 `ci-integration-cov-matrix` 加 GitHub Actions workflow

仍需。`--cov-fail-under=100` 在 pyproject 设了但 CI workflow 不跑。

### 4.4 conda env dev dep 自动装

仍需。chatbiz env 装 `psycopg2-binary` 这次无需(无 alembic integration),
但 `setup-chatbiz-env` 脚本仍需 dev deps 自动装。

### 4.5 TDD micro-cycle 改进

12 个新 test 跨 6 轮 debug,显示 mock-heavy test 写**必须** 1 test → 1 pytest
verify → 写下一个。**不**应**批量写一批**再 verify(`coverage-improvement` /
`gateway-scanner-coverage-matrix` 当时这么干 OK 因 mock 简单;`llm-client-retry-coverage`
暴露了 `MagicMock(spec=httpx.Response)` 时不可批量;sso 进一步确认)。

## 5. Process reflections

### 5.1 credential vs sso 实际 scope 差很大

| Property | credential | sso |
|---|---|---|
| Import errors | 15 (pythonpath fix) | 4 (pythonpath fix) |
| Pre-existing test 数 | 4 | 8 |
| 修 import 后 missing lines | 0 (100% 自带) | 65 (4 module 大量) |
| 需补 test 数 | 0 | 12 (走 8/15 module) |
| 估计时间 | ~30 min | ~1.5-2 hours |

`ci-coverage-all-services/retrospective §4.1` 估"~2 hours" 两个 service,
实际 **sso 吃 80%**,**credential 吃 20%**。**未来** 类似 change 估时间
应**按 service 复杂度**(prod module 数 + 既有 test 数)线性估,不是平均估。

### 5.2 6 artifact 模板复用率 100%

跟 5 个前 coverage change 6 artifact 模板填空 ~30 min 写 + 修。**SSOT
价值** 6 次复用后显现:新 change apply 第一步直接"摸底 6 service 现状"
不需重写 6 artifact 结构。

### 5.3 systematic-debugging 在 mock-heavy test 里的杠杆

sso apply 阶段 6 轮 debug,每轮 1-2 分钟,**总 ~10 分钟**。如果**不**
按 systematic-debugging 4 阶段,可能"猜" 30+ 分钟还没找到根因。每次
debug 都 surface 1 个具体 fail,Evidence → Hypothesis → Test,杠杆高。
