# workflow-engine-ci-cov-matrix — Proposal

## Why

`ci-integration-cov-matrix` (2026-06-15) 加 `ci-cov.yml` 防 cov regression,
matrix 5 service `[audit-and-isolation, credential, gateway-scanner, mcp, sso]`。
当时 retrospective followup "workflow-engine / mcp 2 service 仍是 0% cov":
mcp 由 `mcp-cov-matrix-add` (2026-06-16) 收尾,workflow-engine 待关。

本 change 加 workflow-engine 进 matrix,跟 mcp-cov-matrix-add 同 pattern。
**关键 surface**:摸底(2026-06-16)workflow-engine
`pytest --cov-fail-under=100` 在本机仍 fail(`app/api/workflows.py` 报 miss,
但 print trace + response 验证 list_workflows 实际 100% 执行 — `coverage.py`
7.14.1 analysis 的 false negative)。**CI 跑会 exit 1,PR 暂时 blocked,等独立
followup 修 cov 闸门或 refactor list_workflows 同步走**。

用户(2026-06-16)确认 scope:**仍加 matrix,surface 预期 CI fail**。本
change **不动** cov tool / **不动** list_workflows,只扩 matrix + 同步删
CLAUDE.md 过时描述。

参考:
- `archive/2026-06-15-ci-integration-cov-matrix/proposal.md`
- `archive/2026-06-16-mcp-cov-matrix-add/`
- `archive/2026-06-16-workflow-engine-workflows-coverage/retrospective.md`

## What Changes

**<CI cov matrix 扩到 workflow-engine>**
- From: `.github/workflows/ci-cov.yml` `matrix.service` 列表 5 service
  `[audit-and-isolation, credential, gateway-scanner, mcp, sso]`
- To: 6 service 列表加 `workflow-engine`(alphabetical 第 4 位, 在
  `gateway-scanner` 之后、`mcp` 之前)
- Reason: 关 ci-integration-cov-matrix retrospective workflow-engine followup;
  跟 mcp-cov-matrix-add 同 pattern
- Impact: 跟 mcp-cov-matrix-add **不同** — CI 跑预计会 fail(cov tool false
  negative),PR 暂时 blocked,等独立 followup 修 cov 闸门

**CLAUDE.md "CI 触发约定" 段 matrix 描述 + 过时描述清理**
- From: "当前 matrix 列表 = `[audit-and-isolation, credential, gateway-scanner,
  mcp, sso]`,新增 service 时:..." + 段尾 "**workflow-engine / mcp 2
  service 仍是 0% cov,本约定未触发**"
- To: matrix 列表加 `workflow-engine` + 删过时描述 + 加 1 句"`workflow-engine`
  cov tool false negative 持续,见 `coverage-false-negative-investigation`;
  matrix 已含 6 service"
- Reason: doc ↔ workflow 1:1 + 过时描述清理
- Impact: non-breaking;2 hunk(+1 元素 + 1 段更新 + 删 1 行)

## Capabilities

### New Capabilities
- `workflow-engine-ci-cov-matrix`: 在 `.github/workflows/ci-cov.yml`
  `matrix.service` 列表加 `workflow-engine`(alphabetical 第 4 位);
  在 `CLAUDE.md` "CI 触发约定(强制)" 段 matrix 列表同步加
  `workflow-engine` + 删过时 "workflow-engine / mcp 2 service 仍是 0% cov"
  描述 + 加 cov false negative 1 句说明。**预期 CI 跑 fail(cov tool false
  negative)**,PR 暂时 blocked,等独立 followup 修 cov 闸门或 refactor
  list_workflows 同步走。

### Modified Capabilities
无。本 change 不触及任何现有 spec 的 REQUIREMENT 改动。

## Impact

- **新增文件**:`openspec/changes/workflow-engine-ci-cov-matrix/{brainstorm,
  proposal,design,specs,tasks,plan,retrospective}.md`(7 artifact)
- **修改文件**:
  - `.github/workflows/ci-cov.yml` +1 行(`matrix.service` 列表加
    `- workflow-engine`)
  - `CLAUDE.md` +1 元素 + 删 1 描述 + 加 1 句
- **触及文档**:`openspec/specs/workflow-engine-ci-cov-matrix/spec.md`
  (apply 时 sync)
- **不触及**:
  - 任何 service 代码 / pyproject.toml
  - 任何 docker-compose / 端口表 / 前端
  - `tools/setup-chatbiz-env.sh`(D6 决策 lock)
  - `services/workflow-engine/app/api/workflows.py`(0 行 prod code 改动,
    cov tool false negative 留独立 followup)
- **eng-review 决策引用**:
  - 不触及 12 个 eng-review 锁定决策
  - 跟 CI 触发约定(CLAUDE.md "CI 触发约定(强制)" 段)对齐
- **FUTURE-IMPLEMENTATION**:不适用
- **前端范围**:无前端改动
- **后端范围**:扩 1 个 service 进 CI matrix
- **豁免前端理由**:纯 CI infra
- **3 个具名用户**:不触及
- **非目标**:
  - 不修 cov tool false negative(留独立 followup)
  - 不 refactor list_workflows(留独立 followup)
  - 不扩 ci-cov.yml install step(4 service 共享,扩它会改其它 service)
  - 不拉 workflow-engine 之外的 service 进 matrix
