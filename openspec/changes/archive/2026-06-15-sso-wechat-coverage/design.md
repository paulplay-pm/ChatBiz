## Context

sso service 在 `sso-jwt-utils-coverage` (commit a65b3cb) apply 后,2 module
partial followup 仍 open(retrospective §3.1 + §4.1):

| Module | Missing | 行范围(摸底) |
|---|---|---|
| `app/wechat.py` | **8 miss** | 71-76, 88, 95, 114-115 |
| `app/user.py` | 1 miss | 45 |

本 change **仅关闭 `wechat.py` 8 miss**。1 miss 留 `sso-user-line-45`
后续 1 个 change。

**Stakeholders**: paul(sponsor)/ sso service owner / CI 维护者。

**Constraints**:
- 0 行 prod code 改动
- 不改 `--cov-fail-under=100`(本 change 触发后 sso 总 cov 涨到
  ~99%,`wechat.py` 单 module 100%)
- 沿用既有 pattern(`test_coverage_followup.py` /
  `test_routers_coverage.py` / `test_jwt_utils_coverage.py`)

## Goals / Non-Goals

**Goals:**
1. `app/wechat.py` 从 84% line cov 涨到 100%
2. 5 个新 test 走 5 path 共 8 miss 行(无 `# pragma: no cover`)
3. sso 总 cov 97% → ~99%+
4. 0 行 prod code 改动

**Non-Goals:**
1. 不动 `app/user.py`(仍 followup)
2. 不写 integration test(纯 unit test)
3. 不改 `pyproject.toml` 任何 addopts
4. 不触发 `--cov-fail-under=100` 全模块通过(本 change 仍 1 miss followup)

## Decisions

### D1: 5 test 拆 1 path 1 test

- **选择**: 5 test(timeout / httperror / 其他 errcode / 缺字段 /
  fetch_userinfo httperror)
- **理由**: 1 test → 1 pytest verify → 写下一个(micro-cycle,跟
  `sso-routers-coverage` 锁定);5 path 各自不同 mock 配置,合并会重复
  setup
- **已考虑 alternative**:
  - 4 test 合并 timeout + httperror → 违反 micro-cycle(不同 exception
    class 行为 family 不一致)

### D2: 用 httpx exception mock 不调真网络

- **选择**: `httpx.AsyncClient.get = AsyncMock(side_effect=httpx.TimeoutException/HTTPError(...))`
- **理由**: 0 网络调用,test 快 0.1s/test,跟 `test_coverage_followup.py`
  已有 wechat 2 test 同 pattern

### D3: `fetch_userinfo` 现有 test 用 `side_effect=WorkflowRuntimeError(...)`

- **选择**: 现有 `test_wechat_get_userinfo_raises_workflowruntimeerror_on_5xx`
  是 mock `client.fetch_userinfo = AsyncMock(side_effect=WorkflowRuntimeError(...))`,
  但**实际**是把 mock 装在 `WeChatClient` 实例上,**绕过** `wechat.py`
  内 `try/except` 块(line 107-117)。本 change 需新 1 test 走真
  `httpx.HTTPError` side_effect 触发 try/except body
- **理由**: 走真 `httpx.HTTPError` side_effect,让 `wechat.py` line
  107-117 try/except 块真触发,line 114-115 真的执行
- **已考虑 alternative**:
  - 复用现有 test 加 `monkeypatch` 改 mock → 违反 micro-cycle;现有
    test 验证 `WorkflowRuntimeError` 路径,新 test 验证
    `httpx.HTTPError → WorkflowRuntimeError` 转换路径

### D4: `_available=False` 路径已 100% 覆盖

- **选择**: 不新加 test 走 `_available=False` 路径(行 54-58)
- **理由**: 已被 `test_routers_coverage.py::test_wechat_initiate_503_when_wechat_unavailable`
  间接覆盖(类似:app.state.wechat._available=False),且本 change scope
  只关 8 miss
- **已考虑 alternative**:
  - 补 1 test 走 wechat client 自己的 _available=False → 重复

## Risks / Trade-offs

**[Risk] 5 test 跨 4 个 httpx exception + 2 个数据 variant 4 种 mock 配
置** → Mitigation: 沿用 `test_coverage_followup.py` 已有
`MagicMock(spec=httpx.Response)` + `AsyncMock` 模式,1 test → 1 pytest
verify

**[Trade-off] 5 test 跟 retrospective 估"2-3 test" 偏乐观** → 接受:
估时 fragility 第 8 次轻微触发(本 change 5 test vs 估 2-3 test);但
100% line cov 目标达成,retrospective 估时仅作 sanity check

## Migration Plan

N/A — 本 change **不涉及部署变更**。仅新增
`services/sso/tests/test_wechat_coverage.py`,pytest 跑通即可。

**部署步骤**: 0
**Rollback 策略**: `git revert <commit>` 即可,纯 test 文件
**验收条件**: `pytest tests/test_wechat_coverage.py --cov=app.wechat
--cov-report=term-missing` 5 PASS, `app/wechat.py` 100% line cov

## Open Questions

(本轮无 — D1-D4 决策链已穷举,选完无需进一步澄清)
