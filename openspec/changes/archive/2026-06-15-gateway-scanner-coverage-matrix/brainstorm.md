<!--
Raw capture of superpowers:brainstorming output for
`openspec/changes/gateway-scanner-coverage-matrix`。

本檔原樣捕捉 brainstorming skill 的產出，不強制結構。
Skill 的自然產出通常是 decision log 格式（背景 → 決議鏈 Q1-Qn → 設計取捨），
但依對話內容可能有不同組織方式。

design.md 從本檔萃取並重新整理為結構化設計文件。
不要將本檔的內容複製到 design.md — design.md 是獨立的重組產物，
兩者互補但不重疊。
-->

# Brainstorm: gateway-scanner-coverage-matrix

**Date**: 2026-06-15
**Owner**: paul (sponsor) + Claude (brainstorm facilitator)
**Trigger**: 紧接 `coverage-improvement` change (commit 7fe8e91 archive
完成) 后，立即 follow retrospective §6.4 row 2。

---

## 背景

`openspec/changes/archive/2026-06-15-gateway-egress-enforcement-p0/retrospective.md`
§6.4 row 2：

> | Add `services/gateway-scanner/tests/` to the coverage matrix | `coverage-improvement` |

**关键现状调研**（apply 阶段必须拿到的 evidence，已在 chat 跑过）：

- `services/gateway-scanner/gateway_scanner/scanner.py`：110 stmts，
  38 miss，**65%**
- `services/gateway-scanner/gateway_scanner/__main__.py`：35 stmts，
  35 miss，**0%**（完全没测）
- TOTAL：50%
- 5 个 test file 全部 PASS（40/40）
- `pyproject.toml` 缺 `--cov=gateway_scanner` + `--cov-fail-under=100`
  （对比 `audit-and-isolation/pyproject.toml` 有这俩配置）

**这意味着什么**：row 2 真正意思是"把 gateway-scanner 拉进跟
audit-and-isolation 对齐的 cov 矩阵"——具体两件事：
1. `pyproject.toml` 加 `--cov=gateway_scanner` + `--cov-fail-under=100`
2. 补 test 达到 100%

## 决议链

### Q1: change name 用什么？

- 选项 A：`gateway-scanner-coverage-matrix`（retrospective §6.4 row 2
  原话，措辞调整成 service 限定）
- 选项 B：`gateway-scanner-coverage-100pct`（对齐 `coverage-improvement` 的
  "100pct" 后缀风格）
- 选项 C：`gateway-scanner-pyproject-cov-config`（更窄，限 config 变更）

**决议**：**A** `gateway-scanner-coverage-matrix`。理由：
- 与 retrospective §6.4 row 2 引用链 1:1
- "matrix" 暗示多维度（cov config + test 100% + CI integration），
  跟 row 2 实际意图（"加进矩阵"）契合
- 不缩到 "100pct" 后缀：避免暗示跟 `coverage-improvement` 同 pattern
  重名混淆

**显式拒绝**：
- **B**——跟 `coverage-improvement` 的 "100pct" 后缀重名混淆，本
  change 跟它**性质不同**（改 1 个 config file vs 0 行 prod）
- **C**——scope 比实际窄，**只改 config 不补 test** 等于跑空

### Q2: scope 定多宽？

- 选项 A：修 pyproject + 补 test 达 100%
- 选项 B：同上 + 删 nested 空目录 `services/gateway-scanner/services/gateway-scanner/tests/`
- 选项 C：以上 + 加 GitHub Actions workflow 把 gateway-scanner cov 跑进 CI

**决议**：**A**。理由：
- A 是 retrospective §6.4 row 2 的**字面要求**（"add to the coverage
  matrix" = pyproject config + test 补到 100%）
- B 跨 scope 出了 "coverage" 范围（变成 scaffold 清理）
- C 是 CI 集成改造，scope 远大 3-4x

**显式拒绝**：
- **B**——scaffold 清理是 `scaffold-cleanup` change 的活，不掺到
  coverage change
- **C**——CI workflow 改造是 `ci-coverage-all-services` change 的活

### Q3: `__main__.py` 0% 怎么测？

`__main__.py` 0% missing = 35 stmts,全是 click CLI 入口。标准 pattern:
`click.testing.CliRunner`。

- 选项 A：用 `click.testing.CliRunner.invoke(cli, [...])` 测每个 command
- 选项 B：直接 `subprocess.run([sys.executable, "-m", "gateway_scanner", ...])`
- 选项 C：跳过 `__main__.py`，让 cov fail-under 100% 接受文件级 < 100%

**决议**：**A**。理由：
- `click` 是 prod dep（`pyproject.toml` 第 11 行 `"click>=8.1"`），
  `click.testing` 是 click 内置模块，**零**新 PyPI 依赖
- `CliRunner` 是 click 官方推荐的 CLI test pattern，跨团队熟悉
- 99 行的 CLI 入口，用 `CliRunner` 5-7 个 test 全 cover
- 选项 B subprocess 慢 + 引入额外失败模式（环境变量 / PYTHONPATH）
- 选项 C 接受 < 100% 违反 "fail-under 100%" 配置语义

**显式拒绝**：
- **B**——subprocess 慢 + flake
- **C**——直接否定自己的 fail-under 100% 目标

### Q4: scanner.py 38 missing 怎么补？

scanner.py 38 missing = 错误路径 / 异常处理 / 边界条件。
不能凭 docstring 猜,得看具体 missing lines。

- 选项 A：apply 阶段跑 cov 拿具体 missing lines,逐 line 看代码决定
  test pattern
- 选项 B：直接做 "refactor scanner.py 让它结构化 + 写 test"（超 scope）
- 选项 C：让 coverage matrix config 接受 module-level fail-under
  而不是 file-level

**决议**：**A**。理由：
- 跟 `coverage-improvement` change apply Task 3 同 pattern——跑 cov
  看具体 missing lines,逐个补 test
- 这是 systematic-debugging Phase 1 的"必须看 evidence,不能猜"
- 选项 B 重构超 scope,违反"non-breaking test followup"约束
- 选项 C 是 pytest-cov 配置改造,scope 远大

**显式拒绝**：
- **B**——"重构"是 separate change 的活
- **C**——cov config 改造属"CI config" 类别,不掺

### Q5: nested 空目录 `services/gateway-scanner/services/gateway-scanner/tests/` 怎么处理？

`find services/gateway-scanner/services` 0 个 file——这目录完全是空壳,
估计是 P0 change 期间 scaffold 没清干净。

- 选项 A：本 change 一并删掉
- 选项 B：留待 `scaffold-cleanup` change
- 选项 C：留待 followup

**决议**：**B**。理由：
- 本 change scope 明确是 "coverage matrix",删空目录跨 scope
- 已知 `2026-06-10-implement-audit-and-isolation` change 期间大概率
  引入,留待 `scaffold-cleanup` 统一处理
- "留待 followup" = 默默 deprioritize,跟 record 矛盾

**显式拒绝**：
- **A**——跨 scope,跟 Q2 拒绝 B 同理由
- **C**——等于悄悄 never fix,违反 retrospective 的明确 followup

### Q6: 走完整 openspec 流程吗？

- 选项 A：跟 `coverage-improvement` 同 pattern,8 artifact 全套
- 选项 B：简化 4 artifact（proposal / design / specs / tasks）

**决议**：**A**。理由：
- CLAUDE.md 强制所有 change 走 `openspec/` schemas
- schema `superpowers-bridge` 已是 default,applyRequires = `plan`
- `coverage-improvement` 完整 8 artifact 模板已建立,本 change 复用成本低
- 选项 B 简化 4 artifact 违反 schema,不被允许

**显式拒绝**：
- **B**——schema 强制 9 artifact (含 verify + retrospective 是 apply 阶段)

### Q7: 跳过本地 design doc 走 openspec？

跟 `coverage-improvement` Q6 同问题。

- 选项 A：只写 `openspec/changes/gateway-scanner-coverage-matrix/brainstorm.md`
  (openspec schema 强制),不写 `docs/superpowers/specs/...`
- 选项 B：两个都写（重复内容）

**决议**：**A**。理由：
- 用户在 `coverage-improvement` change 显式选 A
- openspec 自己的 `design.md` artifact 承担"结构化设计"角色
- 避免双写

**显式拒绝**：
- **B**——双写是浪费,openspec 跟 superpowers local design 风格不同

## 设计取捨

### 单一方案：openspec 完整流程

跟 `coverage-improvement` 同 pattern,无"3 个 architecturally distinct
approaches"可比较。apply 阶段会:
1. 跑 cov 拿 missing lines (systematic-debugging Phase 1)
2. surface 给用户决策 (Phase 4 "用户决策杠杆")
3. 补 test 达 100%
4. 改 `pyproject.toml` 加 2 行 config
5. commit + push + archive

### 拒绝的方案汇总

| 方案 | 拒绝理由 |
|---|---|
| Ad-hoc git commit | 违反 CLAUDE.md openspec 流程 |
| 走完整 brainstorming 本地 design doc | 用户已显式跳过,openspec design.md 替代 |
| 关闭 retrospective §6.4 row 1 | `coverage-improvement` change 已关 |
| 删 nested 空目录 | 跨 scope,留 scaffold-cleanup |
| 加 CI workflow | 跨 scope,留 ci-coverage-all-services |
| 重构 scanner.py / __main__.py | 跨 scope,纯 test + config followup |
| subprocess 测 CLI | 慢 + flake,CliRunner 更好 |
| 接受 __main__.py < 100% | 直接否定 fail-under 100% 目标 |
| 简化 4 artifact 流程 | schema 强制 9 artifact |

## Open Questions（本轮未决）

**无**。所有决策在 chat 一次性问完（AskUserQuestion 1 个 Q）,无需二次
澄清。

## Brainstorm facilitator self-check

- [x] 探索了 project context（跑了 pytest --cov,看了 2 个 prod file,
      对比了 audit-and-isolation pyproject.toml）
- [x] 没问视觉问题（纯测试 + config followup,无视觉内容）
- [x] 一次问完 1 个多选题（scope），未多轮往返
- [x] 给出 2-3 approaches + 推荐（Q2 / Q3 / Q4）,其他是 binary decision
- [x] 列出显式拒绝方案 + 理由（见"拒绝的方案汇总"表）
- [x] Open Questions 段明确写"无"，未隐藏未决项
- [x] 决议触及 eng-review 锁定决策？**未触及**——本 change 是测试
      覆盖 followup + 1 行 config 变更,不涉及 12 个 eng-review 决策
      的任何一条
- [x] 决议触及 3 个具名用户 workflow？**未触及**——本 change 改
      `gateway-scanner` 测试,该 service 跟 paul/leo/anny workflow
      都不直接相关（gateway-scanner 是 static-time LLM provider
      SDK import blocker,不是 user-facing）

## 移交到 design.md 的内容

design.md 应从本檔萃取并重组为：
- **Context**: 见上文"背景"段
- **Goals**:
  - G1: `gateway_scanner/scanner.py` 65% → 100%
  - G2: `gateway_scanner/__main__.py` 0% → 100%
  - G3: `services/gateway-scanner/pyproject.toml` 加
    `--cov=gateway_scanner` + `--cov-fail-under=100`
  - G4: 现有 5 个 test file / 40 PASS 不被破坏
- **Decisions**: 见上文"决议链" Q1-Q7
- **Risks**:
  - R1: scanner.py 38 missing 在 apply 阶段才看到具体 lines,补 test
    可能需要 ~5-7 个,数量随 evidence 浮动
  - R2: `__main__.py` 35 missing 全部 CLI 入口逻辑,补 test 需要熟悉
    click CliRunner 模式
  - R3: `pyproject.toml` 改 1 行 addopts 是 prod 改动（非 test 文件），
    跟 `coverage-improvement` "0 行 prod 改动" 不同
- **Migration**: 不适用——`pyproject.toml` 改动是非破坏性,补 test 是
  additive,无 prod 行为变化
