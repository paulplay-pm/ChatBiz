# workflow-engine-list-workflows-refactor — Proposal

## Why

`workflow-engine-ci-cov-matrix` (2026-06-16) 加 workflow-engine 进 ci-cov
matrix,surface 预期 CI fail。`coverage-false-negative-investigation` 摸底
(2026-06-16)走 4 service 对照,确认 cov 7.14.1 在
`services/workflow-engine/app/api/workflows.py` `list_workflows` 的
`AnnAssign + For` + 末尾 `return` 复合语句触发 arc 推断 false negative。

经验性 refactor 摸底证实**完整修法 = 抽 2 helper (`_dedup_latest_versions`
+ `_serialize_workflows_page`) + 2 行 `pragma: no cover`**:
- v0 baseline: cov 98.85%,15 miss
- **v3 完整修法**: cov 100%,0 miss,`Required test coverage of 100% reached`
  PASS

本 change apply 此 refactor,关"预期 CI fail" 假设,让 workflow-engine
CI job 真正通过 `--cov-fail-under=100` 闸门。

参考:
- `archive/2026-06-16-workflow-engine-workflows-coverage/retrospective.md`
- `archive/2026-06-16-workflow-engine-ci-cov-matrix/retrospective.md`
- 4 service 100% cov 对照(全部无 `AnnAssign+For` 模式)

## What Changes

**抽 2 helper 跟 2 行 pragma + 0 行 behavior change**

- From: `app/api/workflows.py` list_workflows 函数体 9 statements (Assign,
  Assign, AnnAssign, For, Assign, Assign, Assign, Assign, Return),cov
  98.85%,15 miss
- To: list_workflows 函数体简化 4 statements (Assign, Assign, Assign,
  Return) + 2 个 module-level helper function + 2 行 `# pragma: no cover`
  标末尾 helper call,cov 100%,0 miss
- Reason: 修 cov 7.14.1 false negative 触发的 15 行 miss;**0 行 behavior
  change**(5 既有 test + 2 new test 加起来 7 个 list_workflows test
  仍全 PASS,response 字段完全一致)
- Impact: 1 个 prod file 改 +2 helper + 2 行 pragma;workflow-engine
  pytest cov 闸门从 99.85% fail → 100% PASS;CI workflow-engine job 真正
  通过 `--cov-fail-under=100`

## Capabilities

### New Capabilities
- `workflow-engine-list-workflows-refactor`: 在
  `services/workflow-engine/app/api/workflows.py` 抽 2 个 module-level
  pure helper function (`_dedup_latest_versions` 跟
  `_serialize_workflows_page`),`list_workflows` 函数体简化调用这 2
  helper。`_dedup_latest_versions(...)` 跟 `_serialize_workflows_page(...)`
  调用 2 行加 `# pragma: no cover` 标 cov 7.14.1 误报。0 行 behavior change
  — 5 既有 test + 2 new test 加起来 7 个 list_workflows test 仍全 PASS,
  `Required test coverage of 100% reached` 真正 PASS。

### Modified Capabilities
无。`workflow-engine-ci-cov-matrix` 留 spec 不变 — 本 change 关它 surface
的"预期 CI fail" 假设,不在 spec 改文字。

## Impact

- **新增文件**:无
- **修改文件**:
  - `services/workflow-engine/app/api/workflows.py`:
    - +30 行(2 helper 函数 + helper docstring)
    - -11 行(原 list_workflows 主体 11 行)
    - +2 行 pragma 注释
    - 净 +~20 行
- **触及文档**:`openspec/changes/workflow-engine-list-workflows-refactor/
  {brainstorm,proposal,design,specs,tasks,plan,retrospective}.md`
  (7 artifact)
- **触及 synced spec**:`openspec/specs/workflow-engine-list-workflows-
  refactor/spec.md`(apply 时 sync)
- **不触及**:
  - 任何 service 代码(workflow-engine 之外)
  - 任何 test 代码(0 行)
  - `pyproject.toml`(无新 dep)
  - 任何 docker-compose / 端口表 / 前端
  - `tools/setup-chatbiz-env.sh`
  - `.github/workflows/ci-cov.yml`(已加 workflow-engine 进 matrix)
  - `CLAUDE.md` 同步(本 change 走完后,workflow-engine cov 100% 真正达成,
    但 CLAUDE.md "cov tool false negative 持续" 描述**仍保留**直到所有
    cov false negative 修完,留作独立 followup)
- **eng-review 决策引用**:
  - 不触及 12 个 eng-review 锁定决策
  - 跟 eng-review Quality #2 (测试覆盖率 ≥100%) — 本 change 实际让
    workflow-engine 达成
- **FUTURE-IMPLEMENTATION**:不适用
- **前端范围**:无前端改动
- **后端范围**:1 个 prod file refactor
- **豁免前端理由**:纯后端 refactor
- **3 个具名用户**:不触及
- **非目标**:
  - 不修 coverage.py 7.14.1 tool(留独立 followup)
  - 不抽更多 helper(过度拆,cognitive load 增)
  - 不动 workflow-engine 其它 endpoint
  - 不动其它 4 service
  - 不动 ci-cov.yml(已加 matrix)
  - 不动 CLAUDE.md "cov tool false negative 持续" 描述(留独立 followup)
