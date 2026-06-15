<!--
Raw capture of superpowers:brainstorming output for
`openspec/changes/ci-coverage-all-services`.

本檔原樣捕捉 brainstorming skill 的產出，不強制結構。
Skill 的自然產出通常是 decision log 格式（背景 → 決議鏈 Q1-Qn → 設計取捨），
但依對話內容可能有不同組織方式。

design.md 從本檔萃取並重新整理為結構化設計文件。
不要將本檔的內容複製到 design.md — design.md 是獨立的重組產物，
兩者互補但不重疊。
-->

# Brainstorm: ci-coverage-all-services

**Date**: 2026-06-15
**Owner**: paul (sponsor) + Claude (brainstorm facilitator)
**Trigger**: 紧接 `llm-client-retry-coverage` (1bb5154) push 后。
`coverage-improvement/retrospective.md §4.4` + `gateway-scanner-coverage-matrix/retrospective.md
§4.3` + `llm-client-retry-coverage/retrospective.md §4.1` 三个 retrospective
都把"覆盖率门槛 propagate" 留为 V1.0+ followup。

---

## 背景

### 现状摸底（apply 阶段 chat 跑过）

| Service | test count | pyproject cov config | 关键 module 100%? |
|---|---|---|---|
| audit-and-isolation | 384 PASS | `--cov=app`,**没** `--cov-fail-under` | 部分:3 module 已 100%(per `coverage-improvement`), `client.py` 也 100%(per `llm-client-retry-coverage`) |
| gateway-scanner | 68 PASS | **没** `--cov` flag | 全 100%(per `gateway-scanner-coverage-matrix`) |
| workflow-engine | 287 PASS | 未摸 | 未摸,63 个 prod python files |
| credential | 4 PASS / 15 ERRORS | 未摸 | test 跑不动,需先修 setup |
| sso | 8 PASS | 未摸 | 未摸,17 个 prod python files |
| mcp | 183 PASS | 未摸 | 未摸,13 个 prod python files |

**6 service pyproject.toml 现状** (verified 跑 chat 命令):
- **0 / 6** 设了 `--cov-fail-under=100` — 这是 P0 retrospective §6.4 row 1+2
  提议的 "cov matrix" 目标**没**真正 enforce
- 2 / 6 (audit-isolation / gateway-scanner) 已有 `--cov` flag 但**没** fail-under
- 4 / 6 (workflow-engine / credential / sso / mcp) 完全没 cov config

### Trigger retrospective §4.1 (llm-client-retry-coverage)

> | coverage 门槛 (`--cov-fail-under=100`) 的 propagate |
> | name: `ci-coverage-all-services` |
> | scope: audit-and-isolation / gateway-scanner / workflow-engine 等 services
>   pyproject.toml 加 `--cov-fail-under=100`,使 cov 数字真正 enforce |
> | estimated effort: 1 session, ~3 commits, ~50 行 config |

### 实际 scope (apply 阶段 evidence 显示)

retrospective 估的"~3 commits, ~50 行 config" **严重低估**:
- 4 个 service(workflow-engine / sso / mcp / credential)**没** 100% cov
- 加 fail-under **必须**先补 test 达 100%,否则 fail-under fail
- credential 跑 4 test 触发 15 errors(setup 错,pre-existing)

**实际 scope = 6 service × (摸 cov + 补 test + 加 fail-under)** = 估计 1-2 周
followup chain。

## 决议链

### Q1: change name 用什么？

- 选项 A: `ci-coverage-all-services`(retrospective §4.1 原话)
- 选项 B: `coverage-fail-under-propagate`(更技术性)
- 选项 C: `coverage-matrix-v1-finalize`(隐含 V1.x 收尾)

**决议**：**A**。理由：
- 与 `coverage-improvement/retrospective.md §4.4` + 3 个 retrospective §4 都用
  "ci-coverage-all-services" 引用
- "all-services" 暗示 6 service 都要改(scope 明确)

**显式拒绝**：
- **B**——`--cov-fail-under=100` 偏技术,retrospective 用 "ci-coverage" 更宽
- **C**——"V1.x finalize" 暗示这个 change close 整个 cov matrix 跟进,但实际
  6 service 还要逐个 sub-change 处理

### Q2: change 性质是 orchestrator / 直接 apply?

- 选项 A: orchestrator change — 产出 6 个 sub-change scaffold,**不**直接改 prod
- 选项 B: 直接 apply — 本 change 直接改 6 service pyproject + 补 test(估计
  1-2 周 work)

**决议**：**A**。理由：
- 单 session 写 6 service × 摸底 + 补 test + 加 fail-under 不现实
- orchestrator change 写 6 artifact 即可,sub-change apply 链分多次
- 未来 audit 能看到"原 change 是 orchestrator,6 个 followup sub-change 各自处理"

**显式拒绝**：
- **B**——1-2 周 work 在单 session 不可能,retrospective 估的"~3 commits" 是
  简化估算,实际需要 6 个 sub-change

### Q3: 6 sub-change 怎么拆?

- 选项 A: per-service 拆 6 change(`ci-coverage-audit-isolation` / `-gateway-scanner` / 等)
- 选项 B: per-status 拆 2 change(`ci-coverage-already-100pct` / `ci-coverage-needs-test`)
- 选项 C: 1 个 mega-change(6 service 一起 apply)

**决议**：**A**。理由：
- per-service 拆最干净,跟 `coverage-improvement` / `gateway-scanner-coverage-matrix` /
  `llm-client-retry-coverage` 同 pattern(每个 change 1 个 capability)
- 每个 sub-change apply 30-45 分钟,未来 audit 清晰
- 6 sub-change 共 ~3-4 小时(分多次 session)

**显式拒绝**：
- **B**——per-status 拆混淆"已 100%"和"未 100%"的差异,未来 grep 难找
- **C**——mega-change 6 service 一起 apply 难,验证难,回滚难

### Q4: 哪些 service 已 100%,哪些要补 test?

apply 阶段 chat 摸过 cov,**结论**:

| Service | 已 100%? | 要补 test? |
|---|---|---|
| audit-and-isolation | 部分(3 module + client.py 已 100%,其他 module 0%) | **是** |
| gateway-scanner | **是**(per `gateway-scanner-coverage-matrix`) | 否,只需加 fail-under |
| workflow-engine | 未摸 | **是** |
| credential | 测试跑不动 | **是**(需先修 15 errors) |
| sso | 未摸 | **是** |
| mcp | 未摸 | **是** |

**5 / 6 service 要补 test**(audit-isolation / workflow-engine / credential /
sso / mcp)。`gateway-scanner` 是 1 个 trivial change(加 fail-under)。

### Q5: `audit-and-isolation` 的 scope 是什么?

retrospective §4.1 说"audit-and-isolation 摸到 100%"。但实际 audit-isolation
有 45 个 prod python files,3 module + client.py 100% 只占总 cov 的一部分。

**决议**: `ci-coverage-audit-isolation` sub-change scope = **摸 audit-isolation
所有 45 file 起点 + 补 test 达 100% on all**。`coverage-improvement` 跟
`llm-client-retry-coverage` 已关 4 module,剩 ~41 module 需补。

### Q6: 怎么修 `credential` 的 15 errors?

`credential` 跑 `pytest tests/` 触 15 errors,可能 missing fixture / env var /
service setup。**不在本 change scope**(本 change 是 orchestrator,具体修复在
`ci-coverage-credential` sub-change 内做)。

**决议**: sub-change 第一步先 surface 15 errors 给用户,决定是修 setup 还是
接受 partial(只测能跑的 4 个 test)。

### Q7: 加 `--cov-fail-under=100` 同时加 `--cov-report=term-missing`?

看 `audit-and-isolation/pyproject.toml`:
```toml
addopts = "-v --cov=app --cov-report=term-missing --cov-fail-under=100"
```

`--cov-report=term-missing` 是显示未覆盖行,**可选**但方便 debug。
`--cov-fail-under=100` 是 enforce。

**决议**: 6 sub-change 加 **2 个** flag,跟 `audit-and-isolation` 对齐。
未来 grep `--cov-fail-under=100` 一致。

### Q8: 走完整 openspec 8 artifact 流程吗?

**决议**：**是**。理由：orchestrator change 跟其他 change 一样需要审计链。

## 设计取捨

### 单一方案：6 sub-change orchestrator

`ci-coverage-all-services` 本身是 **plan-level change**,不直接 apply prod。
产出:
- 6 个 sub-change 的 proposal 草稿(每个 sub-change 一段)
- 6 sub-change 的依赖图(audit-isolation 必须先因最多 module)
- 6 service pyproject 改 pattern 一致性 check

**apply 阶段** = 6 sub-change 用 `openspec new change` 创建 + 写每个 sub-change
的 6 artifact(参考 `coverage-improvement` / `gateway-scanner-coverage-matrix` /
`llm-client-retry-coverage` 模板)+ 各自 apply。

### 拒绝的方案汇总

| 方案 | 拒绝理由 |
|---|---|
| Ad-hoc git commit | 违反 CLAUDE.md openspec 流程 |
| 走完整 brainstorming 本地 design doc | 用户前 3 个 change 显式跳过,openspec design.md 替代 |
| 直接 apply 1-2 周 work | 单 session 不可能,6 service 拆 6 sub-change 更可管理 |
| Per-status 拆 2 change | 混淆"已 100%"和"未 100%"差异,审计难 |
| 1 mega-change 一起 apply | 6 service 一起 apply / 验证 / 回滚难 |

## Open Questions（本轮未决）

**无**。所有决策在 chat 一次性问完,无未决项。

## Brainstorm facilitator self-check

- [x] 探索了 project context(跑了 6 service test count + 摸 pyproject + 摸 prod file count)
- [x] 没问视觉问题
- [x] 一次问完 1 个多选题(scope 拆分)
- [x] 给出 2-3 approaches + 推荐
- [x] 列出显式拒绝方案
- [x] Open Questions 段明确写"无"
- [x] 决议触及 eng-review 锁定决策？**未触及**——纯 config + 拆 sub-change
- [x] 决议触及 3 个具名用户 workflow？**未触及**——ci-coverage 是 internal 工具

## 移交到 design.md 的内容

design.md 应从本檔萃取并重组为：
- **Context**: 见上文"背景"段
- **Goals**:
  - G1: 创建 6 个 sub-change scaffold(`ci-coverage-{audit-isolation,gateway-scanner,workflow-engine,sso,mcp,credential}`)
  - G2: orchestrator 写完 6 sub-change 提案,留 followup chain
  - G3: 6 sub-change 各自走 6 artifact 模板复用
- **Decisions**: 见上文"决议链" Q1-Q8
- **Risks**:
  - R1: 6 sub-change 链估计 1-2 周 followup,team 必须接受多 session apply
  - R2: `credential` 15 errors 修不修是 sub-change 第一步决策
  - R3: `audit-and-isolation` 41 module 摸底范围最大,可能 sub-change 也需拆子
- **Migration**: 不适用
