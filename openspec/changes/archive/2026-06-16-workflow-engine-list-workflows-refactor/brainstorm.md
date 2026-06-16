<!--
Raw capture of superpowers:brainstorming output for
workflow-engine-list-workflows-refactor.

本档原样捕捉 brainstorming skill 的产出。skill 的自然产出是 decision log
格式(背景 → 决策链 Q1-Qn → 设计取舍)。
-->

# Brainstorm: workflow-engine-list-workflows-refactor (decision log)

## 背景

`workflow-engine-ci-cov-matrix` (2026-06-16 archive, commit 501fd4a) 加了
workflow-engine 进 ci-cov matrix,但**预期 CI 会 fail** 因 cov tool false
negative 持续。当时 surface 给独立 followup(修 cov 闸门或 refactor
list_workflows 同步走)。

`coverage-false-negative-investigation` 摸底(2026-06-16)走 4 service
对照,确认:
- `coverage.py` 7.14.1 在 `services/workflow-engine/app/api/workflows.py`
  `list_workflows` 函数体的 `AnnAssign + For` 模式 + 末尾 `return` 复合
  语句触发 arc 推断 false negative
- 4 service 中只有 workflow-engine 1 service 触发;`sso` 5 个 endpoint
  没用 `AnnAssign+For` 模式,`audit-and-isolation` / `credential` /
  `gateway-scanner` 也避开了这模式
- 多种 config 修法 (branch=false / exclude_lines / --cov-branch /
  pragma: no cover 标 prod logic / 降 coverage 版本) 全部走不通或
  拒绝(prama 标 prod logic 掩盖真实 gap,降版本 scope 大)

经验性 refactor 摸底(2026-06-16)证实**完整修法 = 抽 2 helper +
2 行 pragma: no cover**:
- v0 baseline: cov 98.85%,15 miss(line 40-50 + 53-56)
- v1 (1 helper _dedup_latest_versions): cov 99.62%,5 miss
- v2 (2 helper): cov 99.85%,2 miss(line 74 + 76)
- **v3 (2 helper + 2 行 pragma)**: **cov 100.00%,0 miss,
  `Required test coverage of 100% reached` PASS**

摸底实测 289 tests 仍 PASS + `Required test coverage of 100% reached`
文本打出来。

## 项目 context 摸底

- `services/workflow-engine/app/api/workflows.py`:
  - line 25-70 list_workflows 函数体
  - 9 statements: Assign, Assign, AnnAssign, For (5 stmt body), Assign,
    Assign, Assign, Assign, Return
  - 5 个既有 test:test_list_workflows_returns_latest_visible_definitions
    (latest dedup) / search / type / sharing / pagination
  - 2 个 workflow-engine-workflows-coverage 加的 test:empty / dedup
- `services/sso/app/routers/sso.py` 5 个 endpoint 没用 AnnAssign+For 模式,
  全部 100% cov
- `services/audit-and-isolation/app/`, `services/credential/`, `services/
  gateway-scanner/` 4 service 100% cov 摸底**没** AnnAssign+For 模式
- `coverage.py` 7.14.1 是项目 4 service 统一版本,降版本影响 scope 大,
  拒绝

## 决策链

### Q1: refactor 范围?

选项:
- A. 抽 1 个 helper(只 dedup)
- B. 抽 2 个 helper(dedup + serialize)
- C. 抽 3+ helper
- D. 整个 list_workflows 重写

拒绝 A 理由:只抽 dedup 时,v1 测试 cov 99.62% 仍 fail,需要继续抽
serialize 段。
拒绝 C 理由:过度拆,function call overhead + cognitive load。
拒绝 D 理由:0 行 behavior change 原则不破,**最小变更** + 最大 cov 收益
才是 v3。

**选 B**。理由:v3 摸底证实 2 helper + 2 行 pragma = 100% 闸门过。

### Q2: pragma 标哪行?

v2 refactor 后 cov 报 line 74 + 76 miss(2 行):
- line 74: `latest = _dedup_latest_versions(rows, search=search, wf_type=type, sharing=sharing)`
- line 76: `return _serialize_workflows_page(workflows, page=page, page_size=page_size)`

这 2 行是 list_workflows 末尾调用 2 个 helper 的 call。`cov._data.lines()`
不含这 2 行,但 `workflows = sorted(...)` (line 75) 含,说明函数体中间
跑过。**这是 cov 7.14.1 对末尾 return-call + AnnAssign 推断的 arc
false negative**(跟 v0 的 line 40-50 + 53-56 同根因)。

**摸底 print trace 验证 list_workflows 真跑 + response 字段全对**:
- `rows=0` 跟 `rows=3` 都被打印
- response 6 dict field + total=1 / total=1 都对

**pragma: no cover 标 line 74 跟 76 是最小妥协**:
- 标 2 行而非标 11 行(原 line 40-50)
- 标末尾 helper call 而非标 dedup body(避免掩盖真实 cov gap)
- 跟 `services/workflow-engine/app/redis_client.py` line 39-43 已有 precedent

**选标 line 74 + 76**。理由:摸底证实是 cov tool bug 而非真实 miss。

### Q3: 抽 helper 时参数类型怎么处理?

`_dedup_latest_versions` 接 `rows, search, wf_type, sharing`(纯 dict 操作,
无 ORM type 引用)。`wf_type` 而非 `type` 因为 `type` 是 Python built-in。

**选**:helper 函数加 type hints 但 loose(简化摸底,生产代码 follow existing
pattern 即可)。

### Q4: 0 行 behavior change 怎么保证?

- 既有 5 test + 2 new test 加起来 7 个 list_workflows test 全部应仍 PASS
- response 字段 / total / pagination 行为应**完全**一致
- print trace 实测 rows=0 跟 rows=3 都对 + response 6 dict field 全对

**选**:apply 后跑 289 tests 验证 + diff 字段级跟 git main commit 前 commit
对比。

## 开放问题(本轮已决)

无。

## 设计取舍

1. **抽 2 helper 而非 1 或 3+**:v3 摸底证实 2 helper + 2 行 pragma = 100%
2. **pragma 标末尾 helper call 而非 dedup body**:最小掩盖,标真的 cov
   tool bug
3. **0 行 behavior change 严格保持**:5+2 test 全部应仍 PASS
4. **不动 cov tool / 不动其它 4 service**:refactor 单 service scope
5. **不动 CI workflow**(workflow-engine-ci-cov-matrix 之前已加 matrix,
   本 change 关闭它 surface 的"预期 CI fail" 假设)
