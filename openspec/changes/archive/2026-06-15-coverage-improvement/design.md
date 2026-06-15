## Context

`openspec/changes/archive/2026-06-15-gateway-egress-enforcement-p0/retrospective.md`
§6.4 第 1 条记录了 V1.0+ 跟进项：

> | Item | Trigger |
> |---|---|
> | Raise project-wide coverage from 83% → 100% | `coverage-improvement` change |

`audit-and-isolation` 项目在 P0 归档时单元测试覆盖率为
**83.23%**（retrospective §1.1 Stats 引述）。该 gap 的成因是
P0 apply 阶段聚焦 6 个 spec capability 的端到端契约测试，
未对小工具模块（`archive_audit.py` 的 row-count-mismatch 警告
路径、`compute_idempotency_key` 的非 dict/非 str body fallback、
`routing/table.py` 的 Redis pipeline / 失败降级）补充结构性
测试桩。

**当前状态**：
- 2 个测试文件以 **untracked** 状态存在于 working tree（mtime
  2026-06-15 10:14 / 10:43，跟本会话 start 吻合——前会话
  `/clear` 中断的产物）
- 测试内容已写完，且 12 passed / 1 skipped 跑过
- **无** openspec 引用链 — 审计/回溯缺失

**约束**：
- 0 行生产代码修改：纯测试 followup
- 不引入新 PyPI 依赖
- 不动 12 个 eng-review 决策任一条（已验证）
- 不触及 API/DB/前端契约
- V1.0+ 时段：本 change 在 `gateway-egress-enforcement-p0`
  归档后开始，**未**进入 V1.5 / V2.0 路线

**利益相关方**：
- paul（C-level sponsor，retrospective 验收方）
- `audit-and-isolation` service owner（V1.0+ 维护者）
- CI 维护者（确认 `services/audit-and-isolation` 是否有独立
  workflow，本 change 完是否自动纳入 CI）

## Goals / Non-Goals

**Goals:**

- **G1**：让 `services/audit-and-isolation/app/` 下 3 个目标
  模块达到 100% line coverage（pytest-cov 数字）
  - `app/jobs/archive_audit.py`：line 94（`duration_seconds`
    property）+ line 290-295（row-count-mismatch 警告路径）
  - `app/llm/client.py` 的 `compute_idempotency_key`：line
    188-193（非 dict/非 str body fallback）
  - `app/routing/table.py`：load/get 全路径含 Redis 失败
    降级、未知 model 返回 `None`、garbage data fallback
- **G2**：把 2 个 untracked 文件 formalize 进 openspec 审计
  链，提供 `git log --follow` 可追溯的 proposal → design →
  specs → tasks → plan → verify → retrospective 链路
- **G3**：`test_retry_with_idempotency_raises_unreachable_no_result`
  从 broken stub 变为审计友好的 `pytest.skip`，并附 docstring
  说明 `client.py:304` 的 defensive 性质
- **G4**：删除 dead code `await_archive_old_audit_logs` helper
  ，维持测试代码最小集

**Non-Goals:**

- **NG1**：不 close retrospective §6.4 第 2 条（`gateway-scanner`
  测试矩阵）—— 留待后续 change
- **NG2**：不写新生产代码 —— 本 change 是测试 followup，不修
  任何 `app/` 下非 test 文件
- **NG3**：不修补 `app/llm/client.py:304` 的 unreachable 分支
  —— 那是 defensive code，作者已在 sibling `retry_with_redis:121`
  标 `# pragma: no cover`
- **NG4**：不引入覆盖率门槛（`--cov-fail-under=100` 等）——
  那是 CI 配置变更
- **NG5**：不重构 `archive_audit.py` / `routing/table.py` /
  `client.py` 的 prod 代码 —— 假定设计正确，只补 test
- **NG6**：不动 `services/audit-and-isolation/` 之外的任何
  service（`web/`、`workflow-engine/` 等均不动）

## Decisions

### D1: change name = `coverage-improvement`

- **选择**：`coverage-improvement`（与 retrospective §6.4
  原话完全一致）
- **理由**：
  - 与 retrospective §6.4 引用链 1:1，未来 `grep coverage-improvement`
    能从 design doc 追溯到本 change
  - 不带 `-v1-followup` 后缀，避免暗示有 v2 路线图
  - 不缩到 `audit-isolation-coverage-100pct`：留扩展空间给
    未来合入其他 service 的 coverage 桩
- **已考虑 alternative**：
  - `coverage-improvement-v1-followup`（B）：更具体但暗示
    v2 路线，retrospective 没承诺
  - `audit-isolation-coverage-100pct`（C）：范围缩到 service
    级，未来合入其他 service 需重命名

### D2: scope 限于 2 个 untracked 文件

- **选择**：只 close `test_coverage_gaps_v1_followup.py` +
  `test_routing_table_coverage.py`，不碰 gateway-scanner 覆盖
  矩阵
- **理由**：
  - 2 个 untracked 文件都 PASS，evidence 已就位，formalize
    成本低
  - gateway-scanner 矩阵改造需要额外 brainstorm 几轮（扫
    gateway-scanner 现状、缺哪些 test、CI 矩阵改造），scope
    扩大 3-4x
  - "small batches" 是 retrospective §6.4 的措辞，本 change
    跟它一致
- **已考虑 alternative**：
  - 同时 close retrospective §6.4 第 2 条（B）：scope 扩大
    3-4x，超出本 change budget
  - 只 close 1 个文件（C）：浪费已投入工作

### D3: `test_retry_with_idempotency_raises_unreachable_no_result`
→ `pytest.skip`

- **选择**：改 stub 为 `pytest.skip(...)`，docstring 引用
  sibling `retry_with_redis:121` 的 `# pragma: no cover` 约定
- **理由**：
  - `client.py:304` 是 defensive unreachable 分支（需要
    `MAX_ATTEMPTS=0` 才能触发，但 `MAX_ATTEMPTS=3`）
  - 同一文件 line 121 的同模式代码已标 `# pragma: no cover`，
    跟随该约定
  - 保留"我们考虑过 line 304 覆盖"的审计 trail，比删除
    test 信息保留更好
- **已考虑 alternative**：
  - 删掉整个 test：损失审计 trail
  - monkey-patch `MAX_ATTEMPTS = 0` 强行覆盖：测试成本大于
    价值，且违反"测试应反映真实代码路径"原则

### D4: 删 `await_archive_old_audit_logs` dead code

- **选择**：删除该 async helper（`test_coverage_gaps_v1_followup.py`
  line 116-118）
- **理由**：
  - dead code，**全文件零调用点**——实际测试用 `asyncio.run(archive_old_audit_logs(...))`
  - 前会话 debug 残留，mtime 跟本会话 start 吻合
  - 删后覆盖率不变（已 verify）
- **已考虑 alternative**：
  - 保留 helper：dead code 不应留
  - 改 helper 让它有调用方：YAGNI，没真需求

### D5: 走 openspec 完整流程（不 ad-hoc commit）

- **选择**：brainstorm → proposal → design → specs → tasks →
  plan → apply → verify → retrospective 全套
- **理由**：
  - CLAUDE.md 强制"所有 spec/change 走 `openspec/` schemas"
  - schema `superpowers-bridge` 已是 default，applyRequires =
    `plan`
  - 未来审计/回溯需要完整 artifact 链
  - 选项 B 短期省 30 分钟，但下次审 PR 会被回退"违反
    openspec 流程"
- **已考虑 alternative**：
  - ad-hoc `git add` + commit + PR 描述：违反 CLAUDE.md
    openspec 流程；`openspec list` 看不到；CI 审计 trail
    缺失

### D6: 跳过 brainstorming 本地 design doc 落地

- **选择**：只写 `openspec/changes/coverage-improvement/brainstorm.md`
  （openspec schema 的 raw capture），不写 `docs/superpowers/specs/2026-06-15-coverage-improvement-design.md`
- **理由**：
  - 用户显式指令"跳过 design doc，直接走 openspec"
  - openspec 自己的 `design.md` artifact（在 `openspec/changes/<change>/`
    下）承担"结构化设计"角色
  - 避免双写：openspec `design.md` 跟本地 `docs/superpowers/specs/`
    写同样内容是浪费
- **已考虑 alternative**：
  - brainstorming skill 默认路径：写本地 design doc 并
    commit——本 change 不走这条

## Risks / Trade-offs

- **[Risk] R1**：stub test 改成 `pytest.skip` 后，pytest-cov
  数字可能微降（pytest-cov 视 SKIP 为未覆盖）。
  → Mitigation：retrospective §6.4 说"small batches"，本
  change 不承诺绝对 100% 数字；3 个目标模块的"真"测试
  桩都 PASS，覆盖率实质仍提升

- **[Risk] R2**：`test_coverage_gaps_v1_followup.py` 里的
  `test_retry_with_idempotency_raises_unreachable_no_result`
  标 skip 后，未来 review 可能质疑"为什么不直接删"。
  → Mitigation：docstring 显式解释（`MAX_ATTEMPTS=3` 保证
  loop 至少跑一次，line 304 是 defensive unreachable），
  并引用 sibling `retry_with_redis:121` 的先例

- **[Risk] R3**：本 change 完是否自动纳入 CI，取决于
  `services/audit-and-isolation/` 是否有独立 workflow。
  当前 repo grep 显示 4 个 GitHub Actions workflow（按
  c777c00 前 commit history 推断）—— 需要在 task 阶段
  确认。
  → Mitigation：tasks.md 加一个 verification task：跑
  `git log --diff-filter=A --follow --name-only` 跟踪 2
  个文件，确认它们会在 `services/audit-and-isolation`
  现有 CI 路径上被收集

- **[Trade-off] T1**：保留 `test_retry_with_idempotency_raises_unreachable_no_result`
  作为 skip 而非删除 → 接受理由：审计 trail > 文件行数
  最小化

- **[Trade-off] T2**：change name 不带 service 限定（`audit-isolation-coverage-100pct`
  反而更具体）→ 接受理由：retrospective §6.4 用了
  "coverage-improvement" 作为通用 trigger name，留扩展空间

## Migration Plan

N/A — 本 change 不涉及部署变更。

具体说明：
- **不修改**任何 prod 代码、API 端点、DB schema、wire
  protocol
- **不修改**任何 CI workflow 文件
- **不修改**任何 `services/audit-and-isolation/` 之外的
  service
- **不引入**新 PyPI 依赖

**部署顺序**：apply 阶段 2 个 commit 即可：
1. `git add services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`
   + `git commit` —— 1 个 commit
2. `git add services/audit-and-isolation/tests/unit/test_routing_table_coverage.py`
   + `git commit` —— 1 个 commit
（也可合并为 1 个 commit；tasks.md 阶段决定）

**回滚策略**：纯测试 followup，回滚 = `git revert <commit>`，
无生产影响。

**验收条件**：
- `pytest services/audit-and-isolation/tests/unit/test_coverage_gaps_v1_followup.py`
  + `pytest services/audit-and-isolation/tests/unit/test_routing_table_coverage.py`
  → 12 passed, 1 skipped
- `pytest services/audit-and-isolation/tests/unit/ --cov=services/audit-and-isolation/app/jobs/archive_audit --cov=services/audit-and-isolation/app/llm/client --cov=services/audit-and-isolation/app/routing/table --cov-report=term-missing`
  → 3 个目标模块均 100%

## Open Questions

**无**。本 change 是 trivial test followup，所有决策在
brainstorm 阶段一次性问完，无未决项。

- 验证 1：`coverage-improvement` change name 不与已归档
  change 冲突（已用 `ls openspec/changes/archive/` 验证
  无同名）
- 验证 2：eng-review 12 决策无命中（proposal §Impact 已
  显式列 12 条并声明不触及）
- 验证 3：3 个目标模块的 `app/` 路径在 2026-06-15
  c777c00 commit 状态下存在（已用 `find` 验证）
