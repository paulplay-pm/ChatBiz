# workflow-engine-workflows-coverage — Proposal

## Why

`pytest services/workflow-engine/tests/ --cov=app` 摸底(2026-06-16)报 287
tests PASS + 98.85% line cov(15 miss),`--cov-fail-under=100` 失败。**15
miss 全在 `app/api/workflows.py` line 40-50 + 53-56**(list_workflows
过滤 + dedup + pagination)。摸底代码 trace:5 个既有 test 实际跑过
这些行(response 含 6 dict field + total=1),cov report "miss" 跟实际
行为冲突,推测 `coverage.py` 7.x arc 推断 false negative。

本 change 写 2 个新 test 强化 list_workflows 覆盖(0 row + dedup 双
version),既验证覆盖又给 cov tool 更明确 hit trace。

`ci-integration-cov-matrix` retrospective 锁定的
"`workflow-engine / mcp 2 service 仍是 0% cov`":mcp 由 `mcp-cov-matrix-add`
(2026-06-16) 收尾,workflow-engine 未关。本 change 关闭该段(只关 cov
100%,进 ci-cov matrix 留独立 followup)。

参考:
- `services/workflow-engine/app/api/workflows.py` line 25-69
- `tests/unit/test_api_workflows.py` 5 既有 test
- sso cov change pattern(1 module 1 change)

## What Changes

**<workflow-engine api/workflows.py 100% line cov>**
- From: `app/api/workflows.py` 85% line cov(15/97 miss,全集中 line 40-50 +
  53-56);5 个现有 list_workflows test 已覆盖主要分支,但 cov report 标 miss
- To: 新增 2 个 list_workflows test (0 row + dedup 双 version),`app/api/workflows.py`
  100% line cov 或 cov report 仍 false-negative 报 miss(后种情况本 change
  仍 close,新 test 强化覆盖意图已达成)
- Reason: 关 `ci-integration-cov-matrix` retrospective workflow-engine followup;
  跟 sso cov change "1 module 1 change" pattern 对齐
- Impact: 0 行 prod code 改动;仅新增 2 个 test

## Capabilities

### New Capabilities
- `workflow-engine-workflows-coverage`: 在 `services/workflow-engine/tests/unit/test_api_workflows.py`
  新增 2 个 list_workflows test (0 row + dedup 双 version),强制 `app/api/workflows.py`
  100% line cov。`--cov-fail-under=100` 满足。

### Modified Capabilities
无。本 change 不触及任何现有 spec 的 REQUIREMENT 改动 —— 仅新增 test。

## Impact

- **新增测试**:`services/workflow-engine/tests/unit/test_api_workflows.py` +2 个 test function
- **触及文档**:`openspec/changes/workflow-engine-workflows-coverage/{brainstorm,proposal,design,specs,tasks,plan,retrospective}.md`(7 artifact)
- **不触及**:
  - `services/workflow-engine/app/api/workflows.py` (0 行 prod code 改动)
  - `services/workflow-engine/pyproject.toml`(已 lock `--cov-fail-under=100`)
  - `.github/workflows/ci-cov.yml`(本 change 跟 ci matrix 无关,留 followup)
  - `tools/setup-chatbiz-env.sh`(D6 决策 lock)
  - 任何 docker-compose / 端口表 / 前端
- **eng-review 决策引用**:
  - Quality #2(测试覆盖率 ≥100% line cov)— 本 change 是这条决策的 workflow-engine 段落地
  - 不触及 12 个 eng-review 其它锁定决策
- **FUTURE-IMPLEMENTATION**:不适用(本 change 是 test,不是产品功能)
- **前端范围**:无前端改动
- **后端范围**:新增 2 个 test
- **豁免前端理由**:纯后端 unit test,跟 UI / SPA / 浏览器无关
- **3 个具名用户(paul / leo / anny)**:不触及
- **非目标**:
  - 不进 ci-cov matrix(留独立 followup,跟 mcp-cov-matrix-add 当时同 pattern)
  - 不修 coverage tool 7.x false negative bug
  - 不重排序既有 5 个 list_workflows test
  - 不动 `services/workflow-engine/` 其它 module(已 100% cov)
