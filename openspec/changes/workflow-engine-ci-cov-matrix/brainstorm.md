<!--
Raw capture of superpowers:brainstorming output for
workflow-engine-ci-cov-matrix.

本档原样捕捉 brainstorming skill 的产出。skill 的自然产出是 decision log
格式(背景 → 决策链 Q1-Qn → 设计取舍)。
-->

# Brainstorm: workflow-engine-ci-cov-matrix (decision log)

## 背景

`ci-integration-cov-matrix` (2026-06-15 archive, commit 2f538e2) 加了
`.github/workflows/ci-cov.yml` 防 cov regression。当时 retrospective
followup 写"`workflow-engine / mcp 2 service 仍是 0% cov`":mcp 段
由 `mcp-cov-matrix-add` (2026-06-16) 收尾(实际 mcp 早 100% cov 只差进
matrix),workflow-engine 段未关。

本 change 加 workflow-engine 进 ci-cov matrix,跟 mcp-cov-matrix-add
同 pattern。但 workflow-engine 摸底(2026-06-16)确认:
- `pytest services/workflow-engine/tests/ --cov=app --cov-fail-under=100`
  仍 fail(287 PASS / 98.85% cov / 15 miss 全在 `app/api/workflows.py` line
  40-50 + 53-56)
- print trace + response 字段验证 list_workflows 实际 100% 执行,**但
  coverage 7.14.1 analysis 仍报 miss** — 摸底结论是 cov tool false negative
  触发的 `if/continue` + `return { ... }` 复合语句 arc 推断 bug
- 4 service 中只有 workflow-engine 1 service 触发;`audit-and-isolation /
  credential / gateway-scanner / sso` 全部 100% cov
- 多种修法 (branch=false / exclude_lines / --cov-branch / pragma: no cover /
  降 coverage 版本) 全部走不通 — 摸底 surface 结论

**这跟 mcp-cov-matrix-add 当时不同**:mcp 本机 100% cov,CI 100% cov,
加 matrix 后 0 风险。workflow-engine **CI 跑会 fail** (因 `--cov-fail-under=100`
exit 1),PR 暂时 blocked。用户(2026-06-16)确认 scope:**仍加 matrix,
surface 预期 CI 会 fail,跟 raw false negative 同步**。

## 项目 context 摸底

- `ci-integration-cov-matrix` (2026-06-15) 当时 2-commit pattern:
  - `2f538e2 ci(openspec): add ci-cov workflow + CLAUDE.md CI trigger rule`
  - `a8a9d34 chore(openspec): archive ci-integration-cov-matrix`
- `mcp-cov-matrix-add` (2026-06-16) 同 pattern:
  - `0efdbe4 ci(openspec): add mcp to ci-cov matrix`
  - `92150fe chore(openspec): archive mcp-cov-matrix-add`
- matrix 当前 5 service:`[audit-and-isolation, credential, gateway-scanner,
  mcp, sso]`(mcp 已加)
- workflow-engine dev deps (`pyproject [project.optional-dependencies].dev`)
  含 pytest / pytest-asyncio / pytest-cov / httpx / fakeredis / respx /
  aiosqlite / testcontainers[postgres,redis] / ruff / freezegun /
  asgi-lifespan — **比 ci-cov.yml install step 装的 `pytest pytest-cov
  pytest-asyncio respx` 多 7 个**。但 ci-cov.yml 现状只装 4 个最小集合;
  workflow-engine test 是否需要其它 7 个 deps?需要摸底

## 决策链

### Q1: 跟 mcp-cov-matrix-add 1:1 pattern?

- **A**:照 mcp-cov-matrix-add 1:1 pattern(1 行 ci-cov.yml + 1 行
  CLAUDE.md + 5 artifact + 2 commit)
- **B**:开 2 个 change 同步(本 change + 修 cov 闸门)
- **C**:本 change 等 cov 闸门修后再开

**选 A**。理由:用户 2026-06-16 确认 scope 是"仍加 matrix,surface 预期 CI 会
fail"。B 跟 C 会跟用户选 conflict。

### Q2: ci-cov.yml install step 是否要为 workflow-engine 扩?

ci-cov.yml 现状 install step 装 `pytest pytest-cov pytest-asyncio respx`。
workflow-engine dev deps 还有 7 个:httpx / fakeredis / respx / aiosqlite /
testcontainers / ruff / freezegun / asgi-lifespan。

- **A**:本 change 不扩 install step(只改 matrix),依赖 ci-cov.yml 默认装
  的 4 个 deps 够用
- **B**:扩 install step 加装 workflow-engine 实际需要的 deps

**选 A**。理由:ci-cov install step 是所有 service 共享的 4 个最小集合,
扩它会改其它 4 service 的 install 行为(可能引入 regression)。workflow-engine
如果跑 ci 时缺依赖,会在 test 跑时 ModuleNotFoundError,**PR 自然 fail,反
而比 silent pass 更安全**。真要扩,留独立 followup(跟 ci-cov install step
review 一起做)。

### Q3: matrix 顺序

- **A**:alphabetical — workflow-engine 排第 4(在 gateway-scanner 后,
  mcp 前)
- **B**:按 service "重要度"

**选 A**。理由:跟现有 alphabetical 顺序保持一致(已 lock-in)。

### Q4: spec scenario 怎么写?

mcp-cov-matrix-add 当时写了 3 个 scenario(2 个矩阵行为 + 1 个 pre-condition)。
本 change spec 写 3 个 scenario:
1. workflow-engine 在 matrix → 跑 `pytest --cov-fail-under=100`(跟其它
   4 service 同 pattern)
2. matrix 顺序 alphabetical
3. pre-condition:**当且仅当** workflow-engine `pytest --cov-fail-under=100`
   实际通过(exit 0)时 apply 成功 — 但本机 2026-06-16 摸底 fail(cov tool
   false negative),所以**实际 apply 时 pre-condition fail**;spec scenario
   写"pre-condition may fail due to cov tool bug, followup required"

**选 scenario 3** 显式 surface cov tool bug + followup。

### Q5: CLAUDE.md "CI 触发约定" 段 "workflow-engine / mcp 2 service 仍是
0% cov" 描述怎么处理?

CLAUDE.md line 181 现有描述:`**workflow-engine / mcp 2 service 仍是 0% cov,
本约定未触发** — 他们 cov matrix 收尾时一并加`。

本 change 让 workflow-engine 进 matrix → 这描述**整段失效**:
- mcp 已 100% cov(2026-06-16 mcp-cov-matrix-add archive 摸底)
- workflow-engine 实际 100% cov(2026-06-16 workflow-engine-workflows-coverage
  摸底),只是 cov tool false negative 报 miss

**选**:本 change 同步删这段过时描述(从 CLAUDE.md -2 行),换新描述
"`workflow-engine` cov tool false negative 持续,见 `coverage-false-
negative-investigation` retrospective;matrix 已包含 5 service"`。

## 开放问题(本轮已决)

无。

## 设计取舍

1. **CI 会 fail 不阻止本 change apply** — 用户确认 scope 是"仍加 matrix",
   PR 暂时 blocked 留作独立 followup
2. **不动 ci-cov.yml install step** — 4 service 共享,扩它会改其它 service
   install 行为
3. **同步删 CLAUDE.md "workflow-engine / mcp 仍是 0% cov" 描述** —
   已过时
4. **不动 cov tool / 不动 list_workflows refactor** — 留独立 followup
5. **不跟 mcp-cov-matrix-add 合并成 1 个 change** — 2 个独立 service 进
   matrix 保持各自 archived
