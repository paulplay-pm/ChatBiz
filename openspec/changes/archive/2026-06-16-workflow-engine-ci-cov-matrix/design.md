# workflow-engine-ci-cov-matrix — Design

## Context

`ci-integration-cov-matrix` (2026-06-15 archive, commit 2f538e2) 加了
`.github/workflows/ci-cov.yml` 防 cov regression,锁定 `matrix.service = [
audit-and-isolation, credential, gateway-scanner, mcp, sso]`。当时
retrospective followup "`workflow-engine / mcp 2 service 仍是 0% cov`":
mcp 段由 `mcp-cov-matrix-add` (2026-06-16 archive, commit 0efdbe4) 收尾;
workflow-engine 段**待关**。

本 change 加 workflow-engine 进 ci-cov matrix,跟 mcp-cov-matrix-add 同
pattern(1 行 ci-cov.yml + 1 行 CLAUDE.md + 5 artifact + 2 commit)。

**重要 surface(2026-06-16 摸底)**:
- workflow-engine `pytest --cov=app --cov-fail-under=100` 在本机仍 fail
  (98.85% cov, 15 miss 全在 `app/api/workflows.py` line 40-50 + 53-56)
- print trace + response 字段验证 list_workflows 实际 100% 执行
- `coverage.py` 7.14.1 analysis 在该函数复合语句的 false negative 触发的
  arc 推断 bug
- 4 service 中只有 workflow-engine 1 service 触发;其它 4 service 全
  100% cov
- 多种修法 (branch=false / exclude_lines / --cov-branch / pragma: no cover /
  降 coverage 版本) 全部走不通

**这意味着**:本 change apply 后,CI 跑 workflow-engine job 会因
`--cov-fail-under=100` exit 1 fail,PR 暂时 blocked。用户(2026-06-16)
确认 scope:**仍加 matrix,surface 预期 CI fail,跟 raw false negative 同步**。
修 cov 闸门 / refactor list_workflows 留作独立 followup。

## Goals / Non-Goals

**Goals:**
- `.github/workflows/ci-cov.yml` `matrix.service` 列表加 `workflow-engine`
  (alphabetical 第 4 位,在 `gateway-scanner` 之后、`mcp` 之前)
- `CLAUDE.md` "CI 触发约定(强制)" 段 matrix 列表同步加 `workflow-engine`
  + 删过时 "`workflow-engine / mcp 2 service 仍是 0% cov`" 描述 + 加
  cov false negative 1 句说明
- 跟 mcp-cov-matrix-add 1:1 2-commit pattern(feat + archive)
- apply 后 surface 预期 CI 会 fail,在 retrospective 留 followup

**Non-Goals:**
- 不修 cov tool false negative(留独立 followup)
- 不 refactor list_workflows(留独立 followup)
- 不扩 ci-cov.yml install step(4 service 共享,扩它会改其它 service 行为)
- 不拉 workflow-engine 之外的 service 进 matrix
- 不重排序 ci-cov matrix(保持 alphabetical + audit-and-isolation 排头)

## Decisions

### D1: matrix 顺序 alphabetical 第 4 位

- **选择**:`[audit-and-isolation, credential, gateway-scanner, workflow-engine, mcp, sso]`
- **理由**:alphabetical + audit-and-isolation 排头锁定;g 之后是 w
  (workflow-engine),然后 m (mcp) → 第 4 位
- **已考虑 alternative**:
  - 排第 5 (mcp 之后) — 拒绝,违反 alphabetical
  - 排第 1 (audit-and-isolation 之前) — 拒绝,audit-and-isolation 排头 lock
  - 按 "重要度" 排 — 拒绝,YAGNI

### D2: CLAUDE.md 同步删过时描述

- **选择**:删 `**workflow-engine / mcp 2 service 仍是 0% cov,本约定未触发**
  段尾描述`,替换成新段 `**workflow-engine** cov tool false negative 持续,
  见 `coverage-false-negative-investigation`;matrix 已含 6 service`
- **理由**:mcp 已 100% cov(2026-06-16 mcp-cov-matrix-add 摸底),
  workflow-engine 实际 100% cov(2026-06-16 workflow-engine-workflows-
  coverage 摸底),原描述"2 service 仍是 0% cov"已过时
- **已考虑 alternative**:
  - 只改 ci-cov.yml 不动 CLAUDE.md — 拒绝,doc drift
  - 保留原描述 — 拒绝,factually wrong

### D3: 不扩 ci-cov.yml install step

- **选择**:ci-cov.yml install step 保持现状装 `pytest pytest-cov pytest-
  asyncio respx`,不扩 workflow-engine 实际需要的 7 个额外 deps (httpx /
  fakeredis / aiosqlite / testcontainers / ruff / freezegun / asgi-lifespan)
- **理由**:ci-cov install step 是 4 service 共享的 4 个最小集合,扩它会
  改其它 service install 行为(可能引入 regression)。workflow-engine
  如果跑 ci 时缺依赖,会在 test 跑时 ModuleNotFoundError,**PR 自然 fail,
  反而比 silent pass 更安全**
- **已考虑 alternative**:
  - 扩 install step 加装 workflow-engine 实际需要的 deps — 拒绝,scope
    creep,跟 4 service 共用 install step 的设计原则冲突
  - 给 workflow-engine 单开 install step(workflow-engine-specific) —
    拒绝,YAGNI,跟 matrix 设计简化原则冲突

### D4: 不修 cov tool / 不动 list_workflows

- **选择**:本 change 不改 coverage.py 版本 / 不改 list_workflows 源码
- **理由**:user 2026-06-16 确认 scope 是"仍加 matrix",cov 闸门修复留独立
  followup(已有 coverage-false-negative-investigation 摸底结论 + workflow-
  engine-workflows-coverage retrospective 留 followup)
- **已考虑 alternative**:
  - 同步开 1 个 "refactor list_workflows" change — 拒绝,scope creep,
    走 mcp 当时 1:1 pattern

### D5: 不在 spec scenario 写 "CI 必过"

- **选择**:spec scenario 写 "matrix include workflow-engine + ci-cov
  workflow triggers pytest --cov-fail-under=100" 不写 "CI 必过"(因为
  cov tool bug 持续,CI 跑会 fail)
- **理由**:spec 描述 behavior,不是 expected outcome 当 tool bug 持续时
- **已考虑 alternative**:
  - 写 "CI 必过" scenario — 拒绝,会强制 apply 必须等 cov bug 修,
    跟 user "仍加 matrix" scope 冲突

## Risks / Trade-offs

- [Risk] CI 跑 workflow-engine job fail → PR merge blocked
  → Mitigation:apply 后立即在 PR 描述 + retro 写明 "预期 CI fail,等
  followup";独立 followup 修 cov 闸门后,本 change 仍 valid
- [Trade-off] matrix +1 service → GitHub Actions +1 job cost
  → 接受:跟 mcp-cov-matrix-add 同 cost
- [Risk] CLAUDE.md 描述删改可能跟未来 cov bug 修后状态不符
  → Mitigation:retrospective 留 followup "cov bug 修后,删 CLAUDE.md
  'cov tool false negative 持续' 描述"
- [Trade-off] 5 service 共享 install step 不为 workflow-engine 扩 →
  workflow-engine CI 跑可能因缺 dep fail
  → 接受:本 change 预期 CI fail,缺 dep 也算 fail path

## Migration Plan

**N/A — 本 change 不涉及运行时 / DB / endpoint 变更**,只新增 1 行 workflow
matrix 元素 + 改 1 段 CLAUDE.md。Rollback:revert commit 恢复 2 hunk。

**验收条件**(apply 阶段):
1. `.github/workflows/ci-cov.yml` `matrix.service` 列表含 `workflow-engine`
   (alphabetical 第 4 位)
2. `CLAUDE.md` "CI 触发约定(强制)" 段 `当前 matrix 列表` 数组含
   `workflow-engine`
3. `CLAUDE.md` 段尾过时描述 "**workflow-engine / mcp 2 service 仍是 0% cov**"
   删
4. `CLAUDE.md` 段尾加新描述 "**workflow-engine** cov tool false negative
   持续..."
5. `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci-cov.yml'))"`
   验证 yaml 合法
6. `git diff` 只显示 2 处改动(ci-cov.yml +1 行, CLAUDE.md 2-3 hunk)
7. (commit 后) **预期** GitHub Actions 在 workflow-engine job fail(cov tool
   false negative);**预期** mcp + sso + 其它 3 service job 仍 pass

## Open Questions

无。本 change 范围已收敛,所有决策已锁定。
