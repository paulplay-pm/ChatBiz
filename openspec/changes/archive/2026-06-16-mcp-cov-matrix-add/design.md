# mcp-cov-matrix-add — Design

## Context

`ci-integration-cov-matrix` (2026-06-15 archive) 加了 1 个 GitHub Actions
workflow `.github/workflows/ci-cov.yml` 防 cov regression,锁定
`matrix.service = [audit-and-isolation, credential, gateway-scanner, sso]`。
当时 retrospective 写"`workflow-engine / mcp 2 service 仍是 0% cov,本约定
未触发`" —— 摸底(2026-06-16)确认 `mcp` 实际已 100% line cov,只差进 CI matrix
闸门。`workflow-engine` 仍 0% cov,跟本 change scope 无关。

`mcp` 现状(2026-06-16 摸底):
- `pytest services/mcp/tests/ --cov=app --cov-report=term-missing -q`
  → 9 module 全 100% line cov, 183 tests PASS
- `services/mcp/pyproject.toml` `[tool.pytest.ini_options].addopts` 写好
  `--cov=app --cov-report=term-missing --cov-fail-under=100`
- `[project.optional-dependencies].dev` 含 pytest / pytest-asyncio /
  pytest-cov / respx,跟现有 4 service 装的 `pytest pytest-cov pytest-asyncio
  respx` 一致 — ci-cov.yml 的 `Install service + test deps` 段无需扩

## Goals / Non-Goals

**Goals:**
- `.github/workflows/ci-cov.yml` `matrix.service` 列表加 `mcp` (顺序
  alphabetical + audit-and-isolation 排头锁定 → mcp 排第 4,在
  `gateway-scanner` 之后、`sso` 之前)
- `CLAUDE.md` "CI 触发约定(强制)" 段 matrix 列表同步加 `mcp`
- 跟现有 4 service 同 CI cov 100% 闸门,防 mcp cov 滑到 < 100% 时 PR
  失败

**Non-Goals:**
- 不修本机 mcp editable install broken state(`/private/tmp/chatbiz-mcp-fetch/...`
  不存在,跟 CI 无关)
- 不动 `tools/setup-chatbiz-env.sh`(D6 决策 lock 不久,不立刻推翻)
- 不拉 workflow-engine 进 matrix(它仍 0% cov,跟本 change scope 无关)
- 不重排序 ci-cov matrix(保持现有 alphabetical + audit-and-isolation
  排头顺序)
- 不写新 test(mcp 已有 183 tests 100% cov)
- 不改 mcp pyproject / mcp 任何 prod code

## Decisions

### D1: mcp 在 matrix 列表的位置

- **选择**:`[audit-and-isolation, credential, gateway-scanner, mcp, sso]`
  (mcp 排第 4)
- **理由**:alphabetical + audit-and-isolation 排头锁定 → g 之后是 m
  再到 s;跟 ci-cov matrix 现有 4 service 的"按字母序"排列一致
- **已考虑 alternative**:
  - 排第 1(在 audit-and-isolation 之前) — 拒绝,audit-and-isolation 是
    排头锁定(ci-cov.yml 现状)
  - 排第 5(在 sso 之后) — 拒绝,跟字母序不一致
  - 按 service "重要度"重排 — 拒绝,YAGNI

### D2: CLAUDE.md 段同步加 mcp 元素

- **选择**:"CI 触发约定(强制)" 段 `当前 matrix 列表 = [...]` 数组
  加 `mcp`,跟 ci-cov.yml 同序
- **理由**:文档 ↔ workflow 1:1,免 drift
- **已考虑 alternative**:
  - 只改 ci-cov.yml 不动 CLAUDE.md — 拒绝,文档 drift 是技术债
  - 重写整段文档 — 拒绝,scope creep

### D3: 不修 mcp 本机 editable install broken state

- **选择**:本 change 不动本机 env 状态
- **理由**:CI 在自己 VM 跑,跟本机 pip cache 无关。本机 `--check` 报 mcp
  [FAIL] 是 setup-chatbiz-env 独立 followup(用 `--service mcp` 装),跟 CI
  matrix 决策正交
- **已考虑 alternative**:
  - 加 `bash tools/setup-chatbiz-env.sh --service mcp` 进 apply 段
    装本机 mcp — 拒绝,scope creep
  - 改 setup-chatbiz-env.sh SERVICES 数组 + mcp — 拒绝,D6 决策 lock 不久

### D4: 不写新 test

- **选择**:本 change 不动 `services/mcp/tests/`
- **理由**:mcp 已 100% cov 183 tests PASS,无新 requirement
- **已考虑 alternative**:
  - 写 1 个 meta-test 验证 ci-cov.yml 含 mcp — 拒绝,价值低 (CI 跑就够)

### D5: matrix service 顺序保持 alphabetical + audit-and-isolation 排头

- **选择**:不在本 change 引入 re-ordering
- **理由**:scope 严格收窄到 "加 1 元素"
- **已考虑 alternative**:
  - 完全按字母序排(把 audit-and-isolation 排到 a 开头而事实上它是 a 开头 — OK)
  - 按 service "重要度" 排 — 拒绝,YAGNI

## Risks / Trade-offs

- [Trade-off] 本机 mcp editable install broken(CI 无关,但 setup-chatbiz-env
  `--check` 报 mcp [FAIL]) → 接受:本 change 不动本地 env;独立 followup 处理
- [Risk] GitHub Actions 在 mcp 上首次跑可能因 deps cache miss 慢 30-60s
  → Mitigation:既有的 `actions/setup-python@v5` + `conda-incubator/setup-miniconda@v3`
  step 适用所有 Python service;mcp 跟其它 4 service 同 pattern
- [Trade-off] matrix +1 service 意味着 CI 跑 +1 job → 接受:GitHub Actions
  对每 service 独立 job,加 mcp 跟加其它 4 service 同 cost

## Migration Plan

**N/A — 本 change 不涉及运行时 / DB / endpoint 变更**,只新增 1 行
workflow matrix 元素 + 改 1 行 CLAUDE.md 文档。Rollback:revert commit
恢复 2 行(2 个 hunk)。

**验收条件**(apply 阶段):
1. `.github/workflows/ci-cov.yml` `matrix.service` 列表含 `mcp` (alphabetical
   排序,第 4 位)
2. `CLAUDE.md` "CI 触发约定(强制)" 段 `当前 matrix 列表 = [...]` 数组含 `mcp`
3. `bash tools/check-compose-naming.sh`(可选 sanity check)不因本 change 退化
4. `git diff` 只显示 2 处改动(ci-cov.yml +1 行,CLAUDE.md +1 元素),无
   其它 side effect
5. (commit 后) GitHub Actions 在 mcp 上跑通(本机无法直接 verify,等
   push 后 CI 跑)

## Open Questions

无。本 change 范围已收敛,所有决策已锁定。
