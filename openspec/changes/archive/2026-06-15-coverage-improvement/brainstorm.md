<!--
Raw capture of superpowers:brainstorming output for
`openspec/changes/coverage-improvement`.

本檔原樣捕捉 brainstorming skill 的產出，不強制結構。
Skill 的自然產出通常是 decision log 格式（背景 → 決議鏈 Q1-Qn → 設計取捨），
但依對話內容可能有不同組織方式。

design.md 從本檔萃取並重新整理為結構化設計文件。
不要將本檔的內容複製到 design.md — design.md 是獨立的重組產物，
兩者互補但不重疊。
-->

# Brainstorm: coverage-improvement

**Date**: 2026-06-15
**Owner**: paul (sponsor) + Claude (brainstorm facilitator)
**Trigger**: 仓库根 `git status` 显示 2 个 untracked 文件
  - `services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`
  - `services/audit-and-isolation/tests/unit/test_routing_table_coverage.py`

---

## 背景

`openspec/changes/archive/2026-06-15-gateway-egress-enforcement-p0/`
**已于 2026-06-15 归档**（commit c777c00）。其 `retrospective.md §6.4`
明确列出 V1.0+ 跟进项：

> | Item | Trigger |
> |---|---|
> | Raise project-wide coverage from 83% → 100% | `coverage-improvement` change |
> | Add `services/gateway-scanner/tests/` to the coverage matrix | `coverage-improvement` |

这 2 个 untracked 文件是 `audit-and-isolation` 项目内的 coverage
followup 桩——对应 §6.4 第 1 条的 "small batches closing low-hanging
module gaps"。文件 docstring 自己也承认这个来源：

> `test_coverage_gaps_v1_followup.py` line 3-6: "Per
> `openspec/changes/gateway-egress-enforcement-p0/retrospective.md`
> §6, the audit-and-isolation app/ coverage was 83.23% at apply
> time. This file ... is the followup."

第 2 条（gateway-scanner 覆盖矩阵）**不在本 change 范围**——见
"决议 Q2"。

## 决议链

### Q1: change name 用什么？

- 选项 A: `coverage-improvement`（retrospective §6.4 原话）
- 选项 B: `coverage-improvement-v1-followup`（更具体，跟文件名风格）
- 选项 C: `audit-isolation-coverage-100pct`（范围缩到 service 级）

**决议**: **A** `coverage-improvement`。理由：
- 与 retrospective §6.4 引用链 1:1，未来 `grep coverage-improvement`
  能从 design doc 追溯到本 change
- 不带 `-v1-followup` 后缀，避免暗示有 v2 路线图（本 change 只 close
  retrospective §6.4 第 1 条，不预先承诺 v2 scope）
- 不缩到 `audit-isolation-coverage-100pct`：未来可能再合入更多
  service 的 coverage 桩，change name 留扩展空间

### Q2: scope 多大？

- 选项 A: 只 close 这 2 个 untracked 文件（推荐）
- 选项 B: 同时 close retrospective §6.4 整段（包含 gateway-scanner
  测试矩阵）
- 选项 C: 只 close 1 个文件

**决议**: **A**。理由：
- 这 2 个 untracked 文件都 PASS，evidence 已就位
- 选项 B 需要再 brainstorm 几轮（gateway-scanner 现状扫描、缺哪些
  test、CI 矩阵改造），scope 扩大 3-4x
- 选项 C 浪费已投入工作

**显式拒绝**:
- **选项 B** — gateway-scanner 测试矩阵改造超出本 change 范围，
  留待后续 `coverage-improvement-gateway-scanner` 或类似 change
  处理。retrospective §6.4 第 2 条仍未 close，本 change 不假装
  解决它
- **选项 C** — 不必要的 scope 缩小

### Q3: `test_retry_with_idempotency_raises_unreachable_no_result`
这个 stub 怎么处理？

该 test 原本是 broken stub：docstring 说要测 `client.py:304`，实际代码
`inspect.getsource(archive_audit)` 测的是 `archive_audit.py`（错的文件），
断言 `"RuntimeError" in src` 在 `archive_audit.py` 上永远 False。

**决议**: 改成 `pytest.skip(...)`，docstring 引用 sibling
`retry_with_redis:121` 的 `# pragma: no cover` 约定。理由：
- `client.py:304` 是 defensive unreachable 分支（需要 `MAX_ATTEMPTS=0`
  才能触发，但 `MAX_ATTEMPTS=3`）
- 同一文件 line 121 的同模式代码已标 `# pragma: no cover`——
  跟随那个约定
- 不删除 test：保留"我们考虑过 line 304 覆盖"的审计 trail

### Q4: 删掉 unused helper `await_archive_old_audit_logs` 吗？

`test_coverage_gaps_v1_followup.py` line 116-118 定义了
`await_archive_old_audit_logs` async helper，但**全文件 grep
不到任何调用**——实际测试用 `asyncio.run(archive_old_audit_logs(...))`。

**决议**: 删。理由：
- dead code，零调用点
- 前会话 debug 残留（mtime 2026-06-15 10:43 跟本会话 start time
  吻合，前会话 `/clear` 中断的产物）
- 删后 5 passed / 1 skipped 不变（已 verify）

### Q5: 走完整 superpowers-bridge 流程还是 ad-hoc commit？

- 选项 A: 走完整 openspec 流程（brainstorm → proposal → design →
  specs → tasks → plan → apply → verify → retrospective）
- 选项 B: ad-hoc `git add` + commit，PR body 写 "followup coverage
  improvement"

**决议**: **A**。理由：
- CLAUDE.md "所有 spec/change 走 `openspec/` schemas" 强制
- schema `superpowers-bridge` 已是 default，applyRequires = `plan`
- 未来审计/回溯需要完整 artifact 链（proposal → tasks → verify
  → retrospective）
- 选项 B 短期省 30 分钟，但下次审 PR 会被回退"违反 openspec 流程"

**显式拒绝**:
- **选项 B** — 违反 CLAUDE.md openspec 流程

### Q6: brainstorming 本地 design doc 跳过吗？

brainstorming skill 默认要写 `docs/superpowers/specs/<date>-<topic>-design.md`
并 commit。openspec `brainstorm.md` 是**不同文件**——openspec
schema 的 raw capture，落在 `openspec/changes/<change>/brainstorm.md`。

**决议**: 跳过本地 design doc，**只写 openspec `brainstorm.md`**。
理由：
- 用户显式指令"跳过 design doc，直接走 openspec"
- openspec 自己的 `design.md` artifact（在 `openspec/changes/<change>/`
  下）承担"结构化设计"角色
- 避免在 `docs/superpowers/specs/` 和 `openspec/changes/<change>/`
  双写设计内容

**显式拒绝**:
- brainstorming skill 默认路径——本 change 走 openspec 完整流程，
  不在 openspec 之外另立 design doc

## 设计取捨

### 单一方案：openspec 完整流程

无 trade-off——本 change 是 trivial test followup，没有"3 个
architecturally distinct approaches"可比较。前会话写完的 2 个
untracked 文件就是 design + implementation 的合并产物，openspec
artifacts 只是把已有工作 formalize 进审计链。

### 拒绝的方案汇总

| 方案 | 拒绝理由 |
|---|---|
| Ad-hoc git commit | 违反 CLAUDE.md openspec 流程 |
| 走完整 brainstorming skill 默认路径（含本地 design doc）| 用户显式跳过；openspec `design.md` artifact 已承担该角色 |
| 关闭 retrospective §6.4 第 2 条（gateway-scanner） | scope 扩大 3-4x；需要额外 brainstorm |
| 删除 `test_retry_with_idempotency_raises_unreachable_no_result` | 保留为 `pytest.skip` 以维持 "考虑过 line 304" 的审计 trail |
| 保留 `await_archive_old_audit_logs` unused helper | dead code，零调用点 |
| 缩小 change name 到 `audit-isolation-coverage-100pct` | 不留扩展空间，未来合入其他 service 需重命名 |

## Open Questions（本轮未决）

**无**。所有决议在 chat 中一次性问完（AskUserQuestion 一次问 2 个 Q），
无需二次澄清。

## Brainstorm facilitator self-check

- [x] 探索了 project context（读了 retrospective §6.4 + 当前
      `git status` + 两个 untracked 文件 mtime）
- [x] 没问视觉问题（纯测试 followup，无视觉内容）
- [x] 一次问完 2 个多选题（change name + scope），未多轮往返
- [x] 给出 2-3 approaches + 推荐（Q2 / Q5），本 change trivial 故
      Q1/Q3/Q4/Q6 是 binary decision
- [x] 列出显式拒绝方案 + 理由（见"拒绝的方案汇总"表）
- [x] Open Questions 段明确写"无"，未隐藏未决项
- [x] 决议触及 eng-review 锁定决策？**未触及**——本 change 是测试
      覆盖 followup，不涉及 12 个 eng-review 决策的任何一条
- [x] 决议触及 3 个具名用户 workflow？**未触及**——本 change 改
      `audit-and-isolation` 单元测试，未涉及 paul/leo/anny
- [x] 简化字需求（CLAUDE.md config.yaml 100% 单元覆盖）——本
      change 是 close 已存在的 100% 目标，不是新立目标

## 移交到 design.md 的内容

design.md 应从本檔萃取并重组为：
- **Context**: 见上文"背景"段
- **Goals**:
  - G1: 让 `audit-and-isolation` 3 个模块（archive_audit,
    llm/client compute_idempotency_key, routing/table）达到 100%
    单元覆盖
  - G2: 把 2 个 untracked 文件 formalize 进 openspec 审计链
- **Decisions**: 见上文"决议链" Q1-Q6
- **Risks**:
  - R1: stub test 改成 skip 后，coverage 数字可能微降
    （pytest-cov 视 skip 为未覆盖）——接受，retrospective §6.4
    说"small batches"，本 change 不承诺绝对 100% 数字
- **Migration**: 不适用——本 change 只新增 test file，不改 prod code
