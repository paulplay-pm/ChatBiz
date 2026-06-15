## Context

`openspec/changes/archive/2026-06-15-gateway-egress-enforcement-p0/retrospective.md`
§6.4 row 2 记录了 V1.0+ followup：

> | Add `services/gateway-scanner/tests/` to the coverage matrix | `coverage-improvement` change |

紧接 `coverage-improvement` change（commit 7fe8e91 archive 完成）后
立即跟进——row 1 关闭了 `audit-and-isolation` 3 个目标模块的 100%
覆盖，row 2 把同样的标准推广到 `gateway-scanner` 服务。

**当前状态**（apply 阶段跑 cov 摸底）：
- `services/gateway-scanner/gateway_scanner/scanner.py`：110 stmts，
  38 miss，**65%**
- `services/gateway-scanner/gateway_scanner/__main__.py`：35 stmts，
  35 miss，**0%**（完全没测）
- TOTAL：50%
- 5 个 test file 全部 PASS（40/40）：`test_smoke.py` /
  `test_allowlist.py` / `test_blocklist.py` / `test_ast_scanner.py` /
  `test_workflow.py`
- `pyproject.toml` 缺 `--cov=gateway_scanner` + `--cov-fail-under=100`
  （对比 `audit-and-isolation/pyproject.toml` 有这俩配置）
- `services/gateway-scanner/services/gateway-scanner/tests/` 是
  nested 空目录（0 file，scanner scaffold 残留）——**Non-goal NG1**，
  本 change 不删

**约束**：
- 0 行生产代码修改到 `scanner.py` / `__main__.py`（test + config followup）
- 不引入新 PyPI 依赖（`click.testing.CliRunner` 是 prod dep `click>=8.1`
  内置模块）
- 不动 12 个 eng-review 决策任一条（已验证）
- 不触及 API/前端契约（CLI 工具，无前端）

**利益相关方**：
- paul（C-level sponsor，retrospective 验收方）
- `gateway-scanner` service owner（CI / 维护者）
- 跨 service 一致性（让 `audit-and-isolation` 跟 `gateway-scanner`
  对齐到同一 cov 矩阵标准）

## Goals / Non-Goals

**Goals:**

- **G1**：`gateway_scanner/scanner.py` 从 65% 提升到 **100%** line
  coverage（pytest-cov 数字）
- **G2**：`gateway_scanner/__main__.py` 从 0% 提升到 **100%** line
  coverage（含 click CLI 入口用 `click.testing.CliRunner` 测）
- **G3**：`services/gateway-scanner/pyproject.toml` 加
  `--cov=gateway_scanner` + `--cov-fail-under=100` 两行 config，让
  `gateway-scanner` 跟 `audit-and-isolation` 对齐到同一 cov 矩阵
- **G4**：现有 5 个 test file / 40 PASS 保持不变（不被破坏）

**Non-Goals:**

- **NG1**：不删 `services/gateway-scanner/services/gateway-scanner/tests/`
  nested 空目录 —— 留待 `scaffold-cleanup` change
- **NG2**：不加 GitHub Actions workflow 把 gateway-scanner cov 跑进
  CI —— 留待 `ci-coverage-all-services` change
- **NG3**：不改 `scanner.py` / `__main__.py` 任何生产代码 —— 本
  change 是 test + config followup，不重构
- **NG4**：不引入新 PyPI 依赖 —— `click.testing.CliRunner` 是
  `click` 内置
- **NG5**：不重新打开 `coverage-improvement` change 的范围 —— 本
  change 范围明确限 `gateway-scanner`，不动 `audit-and-isolation`
- **NG6**：不重新打开 `cli-invocation-argparse-migration` 之类历史
  change —— `__main__.py` 0% 补 test 走 `CliRunner` 标准 pattern
- **NG7**：不暴露 `__main__.py` 内部 helper 函数（保持 `_` 前缀私有）——
  test 通过 `click.testing.CliRunner` 间接走 cli 入口

## Decisions

### D1：change name = `gateway-scanner-coverage-matrix`

- **选择**：`gateway-scanner-coverage-matrix`
- **理由**：
  - 与 retrospective §6.4 row 2 引用链 1:1
  - "matrix" 暗示多维度（cov config + test 100% + CI integration），
    跟 row 2 "add to the coverage matrix" 实际意图契合
  - 不缩到 "100pct" 后缀：避免跟 `coverage-improvement` 同 pattern
    重名混淆
- **已考虑 alternative**：
  - `gateway-scanner-coverage-100pct`（B）：跟 `coverage-improvement`
    风格对齐但重名混淆
  - `gateway-scanner-pyproject-cov-config`（C）：scope 比实际窄，
    只改 config 不补 test 等于跑空

### D2：scope = 修 pyproject + 补 test 达 100%

- **选择**：改 1 行 config + 补 ~5-7 个 test
- **理由**：
  - 是 retrospective §6.4 row 2 的**字面要求**（"add to the coverage
    matrix" = config + test 补到 100%）
  - 跟 `coverage-improvement` change apply Task 3 同 pattern——跑
    cov 看 missing lines,逐个补 test
- **已考虑 alternative**：
  - B（加删 nested 空目录）：跨 scope
  - C（加 CI workflow）：跨 scope，scope 远大 3-4x

### D3：`__main__.py` 用 `click.testing.CliRunner` 测 CLI

- **选择**：`click.testing.CliRunner.invoke(cli, [...])` 测每个
  command
- **理由**：
  - `click` 是 prod dep（`pyproject.toml` 第 11 行 `"click>=8.1"`），
    `click.testing` 是 click 内置模块，**零**新 PyPI 依赖
  - `CliRunner` 是 click 官方推荐的 CLI test pattern，跨团队熟悉
  - 99 行的 CLI 入口，用 `CliRunner` 5-7 个 test 全 cover
- **已考虑 alternative**：
  - subprocess 跑 `python -m gateway_scanner`：慢 + flake
  - 跳过 `__main__.py`，接受 cov < 100%：直接否定 fail-under 100%

### D4：scanner.py 38 missing 走 systematic-debugging 路径补

- **选择**：apply 阶段跑 cov 拿具体 missing lines,逐 line 看代码决定
  test pattern
- **理由**：
  - 跟 `coverage-improvement` change apply Task 3 同 pattern——跑 cov
    看具体 missing lines,逐个补 test
  - 这是 systematic-debugging Phase 1 的"必须看 evidence,不能猜"
- **已考虑 alternative**：
  - 重构 scanner.py 让它结构化（超 scope）
  - 改 pytest-cov config 接受 module-level fail-under（属 CI config
    改造,scope 远大）

### D5：nested 空目录 `services/gateway-scanner/services/gateway-scanner/tests/` 留待 scaffold-cleanup

- **选择**：本 change 不删
- **理由**：
  - 跨 scope 出了 "coverage" 范围（变成 scaffold 清理）
  - 已知 `2026-06-10-implement-audit-and-isolation` change 期间大概率
    引入,留待 `scaffold-cleanup` 统一处理
- **已考虑 alternative**：
  - 本 change 一并删掉（跨 scope,跟 D2 拒绝 B 同理由）

### D6：走完整 openspec 8 artifact 流程

- **选择**：brainstorm → proposal → design → specs → tasks → plan
  → apply → verify → retrospective
- **理由**：
  - CLAUDE.md 强制所有 change 走 `openspec/` schemas
  - schema `superpowers-bridge` 已是 default,applyRequires = `plan`
  - `coverage-improvement` 完整 8 artifact 模板已建立,本 change 复用
    成本低
- **已考虑 alternative**：
  - 简化 4 artifact（proposal / design / specs / tasks）：schema 强制
    9 artifact,不允许简化

### D7：跳过本地 design doc 走 openspec

- **选择**：只写 `openspec/changes/gateway-scanner-coverage-matrix/brainstorm.md`
  (openspec schema 强制),不写 `docs/superpowers/specs/...`
- **理由**：
  - 用户在 `coverage-improvement` change 显式选 A
  - openspec 自己的 `design.md` artifact 承担"结构化设计"角色
  - 避免双写
- **已考虑 alternative**：
  - 两个都写（双写浪费,openspec 跟 superpowers local design 风格不同）

## Risks / Trade-offs

- **[Risk] R1**：scanner.py 38 missing 在 apply 阶段才看到具体
  lines,补 test 可能需要 ~5-7 个,数量随 evidence 浮动
  → Mitigation：apply 阶段跑 cov 后 surface 给用户决策,跟
  `coverage-improvement` apply Task 3 同 pattern

- **[Risk] R2**：`__main__.py` 35 missing 全部 CLI 入口逻辑,补 test
  需要熟悉 click `CliRunner` 模式
  → Mitigation：`click.testing.CliRunner` 是 click 内置标准 pattern,
  无学习曲线

- **[Risk] R3**：`pyproject.toml` 改 1 行 `addopts` 是 prod 改动
  (非 test 文件),跟 `coverage-improvement` "0 行 prod 改动" 不同
  → Mitigation:proposal.md §Impact 已显式列"non-breaking.prod 行为
  不变,test-time 行为变更";`--cov` 跟 `--cov-fail-under` 只在 pytest
  跑测试时生效,无 prod 影响

- **[Risk] R4**：如果补 test 不足 + 加 `--cov-fail-under=100` 后
  pytest 直接 fail（coverage < 100%）→ apply Task 2 失败
  → Mitigation:apply Task 2 跑 pytest 验证 → 失败时立即停,补 test,
  不 commit（已 plan）

- **[Trade-off] T1**：保留 nested 空目录 → 接受理由:跨 scope 出
  了 coverage,留 scaffold-cleanup

- **[Trade-off] T2**：`--cov=gateway_scanner` + `--cov-fail-under=100`
  在 pytest 默认行为变严,可能 catch 现有 40 PASS 的细微覆盖问题
  → 接受理由:这正是 row 2 想要的——把 coverage matrix 拉到跟
  audit-and-isolation 同标准;任何"现有 PASS 但 cover 不全"会显式
  surface 给用户

## Migration Plan

N/A — 本 change **不**涉及部署变更。

**具体说明**：
- 不修改 `gateway_scanner/scanner.py` / `__main__.py` 任何生产代码
- 不修改任何 CLI command / AST scanner 行为 / blocklist/allowlist 逻辑
- `pyproject.toml` config 变更是 test-time 行为,prod 行为不变
- 不引入新 PyPI 依赖
- 不动 `services/gateway-scanner/` 之外任何 service

**部署顺序**（apply 阶段）：
1. 改 `pyproject.toml` addopts（1 commit 包含）
2. 跑 cov 看 missing（验证 evidence）
3. surface 给用户决策（systematic-debugging Phase 4 用户决策杠杆）
4. 补 test 达 100%
5. 单 commit（不拆，跟 `coverage-improvement` 一致）
6. openspec archive

**回滚策略**：
- 纯 test + config followup，回滚 = `git revert <commit>` + 把
  `pyproject.toml` 还原 addopts = `"-v"`
- 无生产影响
- 无 CI 自动化介入（NG2）

**验收条件**：
- `pytest services/gateway-scanner/tests/` → 全 PASS（保持 40+ 个,
  加上新 test）
- `pytest services/gateway-scanner/tests/ --cov=gateway_scanner
  --cov-fail-under=100` → 全 PASS,**且** 退出码 0（fail-under 100%
  不报 coverage 不够）
- `git diff services/gateway-scanner/gateway_scanner/` 输出为空
  （0 行生产代码修改）
- `git diff services/gateway-scanner/pyproject.toml` 显示
  `addopts` 增 2 行 config

## Open Questions

**无**。本 change 是 trivial config + test followup,所有决策在
brainstorm 阶段一次性问完,无未决项。

- 验证 1：`gateway-scanner-coverage-matrix` change name 不与已
  归档 change 冲突（已用 `ls openspec/changes/archive/` 验证无同名）
- 验证 2：eng-review 12 决策无命中（proposal §Impact 已显式列 12 条
  并声明不触及）
- 验证 3：2 个 prod file 在 2026-06-15 c777c00 commit 状态下存在
  （已用 `find` 验证）
- 验证 4：现有 5 个 test file 40 PASS（已用 `pytest --cov` 验证）
