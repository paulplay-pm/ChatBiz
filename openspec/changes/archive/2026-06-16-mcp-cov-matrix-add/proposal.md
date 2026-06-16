# mcp-cov-matrix-add — Proposal

## Why

`ci-integration-cov-matrix` (2026-06-15 archive, commit 2f538e2) 加了
`.github/workflows/ci-cov.yml` 防 cov regression,锁定
`matrix.service = [audit-and-isolation, credential, gateway-scanner, sso]`。
当时 retrospective 写"`mcp` 仍是 0% cov,本约定未触发" —— **此描述事实错**。
摸底(2026-06-16)确认 `mcp` 实际已 100% line cov:9 module 全 100%, 183 tests
PASS,Required test coverage of 100% reached。`services/mcp/pyproject.toml`
`addopts` 也已写好 `--cov-fail-under=100`。**唯独** ci-cov.yml
`matrix.service` 没列 mcp,所以 PR merge main 时 mcp 没有 cov 100% 闸门。

本 change 收尾 ci-integration-cov-matrix retrospective 锁定的 followup,
把 mcp 加进 CI matrix 闸门(防 regression),与现有 4 service 同 pattern。

参考源:
- `openspec/changes/archive/2026-06-15-ci-integration-cov-matrix/proposal.md`(本 change 模板)
- `openspec/changes/archive/2026-06-15-ci-integration-cov-matrix/design.md`(CI workflow design)
- `CLAUDE.md` "CI 触发约定(强制)" 段
- `services/mcp/pyproject.toml`(已 lock `--cov-fail-under=100`)

## What Changes

**<CI cov matrix 扩到 mcp>**
- From: `.github/workflows/ci-cov.yml` `matrix.service` 列表
  `[audit-and-isolation, credential, gateway-scanner, sso]`,无 mcp
- To: 列表加 `mcp` → `[audit-and-isolation, credential, gateway-scanner, mcp, sso]`
- Reason: 关 ci-integration-cov-matrix retrospective followup;跟现有 4 service
  同 CI cov 100% 闸门,防 mcp cov 滑到 < 100% 时无 PR 失败
- Impact: non-breaking;新 service 加 1 元素,既有 workflow 不变

**CLAUDE.md "CI 触发约定" 段 matrix 描述**
- From: "当前 matrix 列表 = `[audit-and-isolation, credential, gateway-scanner,
  sso]`,新增 service 时:..."
- To: "当前 matrix 列表 = `[audit-and-isolation, credential, gateway-scanner,
  mcp, sso]`,新增 service 时:..."
- Reason: 跟 ci-cov.yml 同步,文档 ↔ workflow 1:1
- Impact: non-breaking;1 元素加进已有 matrix 列表

## Capabilities

### New Capabilities
- `mcp-cov-matrix-add`: 在 `.github/workflows/ci-cov.yml` 的 `matrix.service`
  列表加 `mcp` (顺序第 4,在 `gateway-scanner` 之后、`sso` 之前);
  在 `CLAUDE.md` "CI 触发约定(强制)" 段 matrix 列表同步加 `mcp`。
  无新 workflow 段、无新 install step、无新 prod code 改动。

### Modified Capabilities
无。本 change 不触及任何现有 spec 的 REQUIREMENT 改动 —— 仅扩 1 个
CI infrastructure list 元素 + 1 段文档 list 元素。

## Impact

- **新增文件**:`openspec/changes/mcp-cov-matrix-add/{brainstorm,proposal,
  design,specs,tasks,plan,retrospective}.md`(7 artifact)
- **修改文件**:
  - `.github/workflows/ci-cov.yml` +1 行(`matrix.service` 列表加 `- mcp`)
  - `CLAUDE.md` +1 元素(matrix 列表加 `mcp`)
- **触及文档**:`openspec/specs/mcp-cov-matrix-add/spec.md`(apply 时 sync)
- **不触及**:
  - 任何 service 代码 / pyproject.toml
  - 任何 docker-compose / 端口表 / 前端
  - `tools/setup-chatbiz-env.sh`(D6 决策 1 session 内 lock,不立刻推翻)
  - `services/workflow-engine/` (本 change 跟它无关)
- **eng-review 决策引用**:
  - 不触及 12 个 eng-review 锁定决策
  - 跟 CI 触发约定(CLAUDE.md "CI 触发约定(强制)" 段)对齐:
    step 1 pyproject 已 lock; step 2 加进 workflow matrix(本 change 主体);
    step 3 PR 描述登记(本 change)
- **FUTURE-IMPLEMENTATION**:不适用(本 change 是 CI infrastructure,不是产品功能)
- **前端范围**:无前端改动(纯 CI + 文档)
- **后端范围**:扩 1 个 service 进 CI matrix
- **豁免前端理由**:纯 CI infra,跟 UI / SPA / 浏览器无关
- **3 个具名用户(paul / leo / anny)**:不触及(本 change 是工程 CI infra,不是用户功能)
- **非目标**:
  - 不修本机 mcp editable install broken state(`/private/tmp/chatbiz-mcp-fetch/...`
    不存在,跟 CI 无关)
  - 不动 `tools/setup-chatbiz-env.sh` 的 SERVICES 数组
  - 不拉 workflow-engine 进 matrix(它仍 0% cov,跟本 change scope 无关)
  - 不重排序 ci-cov matrix(保持现有 alphabetical + audit-and-isolation 排头顺序)
