<!--
Raw capture of superpowers:brainstorming output for
workflow-engine-workflows-coverage.

本档原样捕捉 brainstorming skill 的产出。skill 的自然产出是 decision log
格式(背景 → 决策链 Q1-Qn → 设计取舍)。

design.md 从本档萃取并重新整理为结构化设计文件。
-->

# Brainstorm: workflow-engine-workflows-coverage (decision log)

## 背景

`pytest services/workflow-engine/tests/ --cov=app` 摸底结果(2026-06-16):
- 287 tests PASS
- 56/57 module 已 100% line cov
- **唯一未 100%**:`app/api/workflows.py` 85%(15 miss: line 40-50 + 53-56)
- 总体 98.85% — `--cov-fail-under=100` 失败,exit 1

`ci-integration-cov-matrix` (2026-06-15) retrospective 锁定的 followup
"`workflow-engine / mcp 2 service 仍是 0% cov,本约定未触发`":mcp 部分
由 `mcp-cov-matrix-add` (2026-06-16) 收尾(实际 mcp 早 100% cov,
只差进 CI matrix),workflow-engine 部分未关。

**摸底细节**:
- list_workflows endpoint(line 25-69)接 4 个 query param:
  `search` / `type` / `sharing` / `page+page_size`
- 现有 5 个 test 覆盖:search / type / sharing / pagination / latest dedup
- 摸底代码 trace:`test_list_workflows_search_filters_by_name` 加 2 row
  + GET /workflows?search=alpha → response 含全部 6 个 dict field
  + total=1,说明 list_workflows 函数体 line 35-69 实际跑过
- coverage report 标 "40-50, 53-56 miss" 跟实际行为不符,**可能是
  coverage 7.x arc 推断的 false negative**

## 项目 context 摸底

- `services/workflow-engine/tests/unit/test_api_workflows.py` 已有
  19 个 test(line 1-130+ 已读),其中 5 个针对 list_workflows
- conftest fixture:`db_setup`(in-memory SQLite,每 test 独立) /
  `client`(LifespanManager + AsyncClient) / `auth_headers`(`X-User-Id: test-user`)
- sso cov change pattern(1 module 1 change)同样适用本 change
- workflow-engine 不进 ci-cov matrix(eng-review 锁定的 ci matrix 4 service
  是 audit-and-isolation / credential / gateway-scanner / sso,workflow-engine
  + mcp 收尾时再扩);本 change 只关"workflow-engine 100% line cov",matrix
  加入留作独立 followup

## 决策链

### Q1: 本 change scope 收窄到什么?

选项:
- A. 写 1-2 个新 test 强化 list_workflows line 40-50 + 53-56 覆盖
- B. A + 同时把 workflow-engine 加进 ci-cov matrix
- C. 调查 coverage 7.x false negative bug,直接修 coverage 配置
- D. 接受 cov 98.85% 现状,降级 `--cov-fail-under` 到 99(破例)

拒绝 B / C / D:
- B:scope creep,本 change 跟 ci-cov matrix 无关,跟 mcp-cov-matrix-add
  当时同 pattern(那时也是先 cov 100% 后 matrix 加)
- C:coverage 7.x 的 arc 推断是 tool 内部行为,改 coverage 配置可能
  引入新 false positive,治标不治本
- D:本仓库 CLAUDE.md 锁定 100% line cov 是 eng-review Quality #2,
  降级等于违反 eng-review 决策

**选 A**。理由:跟 sso cov change 1 module 1 change pattern 一致,scope
严格收窄到 1 个 module 的 line cov gap。

### Q2: 写几个新 test?

选项:
- A. 1 个 test,覆盖 line 40-50 + 53-56 全部分支
- B. 2-3 个 test,每个覆盖 1 个独立分支
- C. 0 个 test,只调现有 5 个 test 的 assertion / mock 让 line 跑过

拒绝 C:**测试覆盖率条款 per `openspec/config.yaml` 强制 ≥100% / 安全全覆盖,
不允许"先实现后补测试"**。新增 test 是正确路径。
A 也可,但 B 跟 sso cov change "1 test → 1 pytest verify" 的 micro-cycle
更对齐,易调试。

**选 B**。理由:2-3 个独立 test,每个覆盖 list_workflows 1 个未覆盖
分支(0 row / dedup 双 version / pagination edge case)。

### Q3: 测哪几个分支?

摸底 list_workflows 5 既有 test + line 40-50 + 53-56 实际 line content:
- 40-50 过滤 + dedup(11 行)
- 53-56 pagination + return start(4 行)
- 现有 5 个 test 实际行为:
  - `test_list_workflows_returns_latest_visible_definitions`:v1+v2 同 id
    → dedup 跑(line 49-50)
  - `test_list_workflows_search_filters_by_name`:search="alpha" 1 match
    + 1 skip → line 42-43 跑
  - `test_list_workflows_type_filter`:type="chatflow" 1 match + 1 skip
    → line 45-46 跑
  - `test_list_workflows_sharing_filter`:sharing="team" 1 match + 1 skip
    → line 47-48 跑
  - `test_list_workflows_pagination`:3 row + page=1 size=2 + page=2 size=2
    → line 54-55 跑

**所有 15 miss 行的 line 40-50 + 53-56 都被 5 个 test 覆盖**:
- 40, 41, 44, 49, 50, 52 — 5 test 都跑
- 42-43, 45-46, 47-48 — search / type / sharing 3 test 覆盖
- 53, 54, 55, 56 — pagination test 覆盖

所以 coverage report "miss 40-50, 53-56" 跟实际行为冲突 → cov tool bug
或 arc 推断 false negative。

新增 2-3 个 test 的策略:
- 1 个测 0 row(empty list_workflows 走 line 40 + 41 但 for 0 次)
- 1 个测 dedup 同 id 多 version 多次添加(强化 line 49-50)
- 1 个测 page_size > total(page > 1 size > total 返回空 list)

**最终选 2 个 test**(0 row + dedup 强化),page_size 边界 case 跟现有
pagination test 重叠。

### Q4: 摸底阶段确认 cov 100% 后,是否还动 ci-cov matrix?

**否**。跟 mcp-cov-matrix-add 当时同 pattern:先关 cov gap → 然后
独立 followup 加进 ci-cov matrix。本 change 只关 cov 100%。

## 开放问题(本轮已决)

无。

## 设计取舍

1. **写 2 个新 test 而非 1 个或 0 个**:跟 sso cov change "1 test → 1 pytest
   verify" micro-cycle 对齐;0 个 test 违反 openspec 100% line cov +
   不允许"先实现后补测试"双重约束
2. **不修 coverage tool bug**:改 coverage 配置 / 降版本是 toolchain 改动,
   scope creep,留独立 followup
3. **不动 ci-cov matrix**:本 change 跟 matrix 无关,留独立 followup
4. **不查 row 0 之外的 edge case**:`type` 参数的 falsy 路径(`type=""`)
   `sharing` 类似 — 现有 5 test 已覆盖,新增 test 专注 line 40-50 的 0-row
   跟 dedup 强化
