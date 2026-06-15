## Context

`ci-coverage-all-services` 是 **orchestrator change**,不直接改 prod code。
本 change 跟之前 3 个 coverage change (`coverage-improvement` /
`gateway-scanner-coverage-matrix` / `llm-client-retry-coverage`)性质不同:
前 3 个是单 service 100% line coverage 落地,本 change 是把"覆盖率门槛
真正 enforce 到 CI"作为 meta-change,产出 6 个 sub-change scaffold 让
team 后续 1-2 周分多次 session 逐个 apply。

**当前状态**(apply 阶段 chat 跑过):

| Service | test count | pyproject cov config | 关键 module 100%? |
|---|---|---|---|
| audit-and-isolation | 384 PASS | `--cov=app`,**没** `--cov-fail-under` | 部分:3 module + client.py 100% |
| gateway-scanner | 68 PASS | **没** `--cov` flag | 全 100% |
| workflow-engine | 287 PASS | 未摸 | 未摸,63 prod file |
| credential | 4 PASS / 15 errors | 未摸 | 测试跑不动,需先修 15 errors |
| sso | 8 PASS | 未摸 | 未摸,17 prod file |
| mcp | 183 PASS | 未摸 | 未摸,13 prod file |

**约束**:
- 0 行 production code 改动到本 change(只在 6 sub-change 各自 apply)
- 0 行 pytest-cov 装(已锁 dev dep)
- 不动 12 个 eng-review 决策任一条
- 不触及 API/前端契约
- 本 change **必须**产出 followup task list + sub-change scaffold

**利益相关方**:
- paul(C-level sponsor,3 个 retrospective 共同提议方)
- 6 service owners(各自 sub-change apply 责任方)
- CI 维护者(future `ci-coverage-all-services` 完自动跑 cov 100% check)

## Goals / Non-Goals

**Goals:**

- **G1**: 创建 6 个 sub-change scaffold(`openspec/changes/ci-coverage-{svc}/`)
  并写每个 sub-change 的 proposal 草稿
- **G2**: 6 sub-change 各自独立可 apply(不互相依赖,顺序可调)
- **G3**: 给每个 sub-change 写清楚"摸 cov 起点 + 补 test 达 100% + 加 fail-under"
  的 apply 流程
- **G4**: 6 sub-change 共用同 1 套 6 artifact 模板,降低 future apply 时间

**Non-Goals:**

- **NG1**: 本 change 不直接 apply 6 service pyproject —— 6 sub-change 各自 apply
- **NG2**: 本 change 不直接补 6 service 的 test —— 6 sub-change 各自 apply
- **NG3**: 本 change 不修 `credential` 15 errors —— sub-change 第一步处理
- **NG4**: 不加 GitHub Actions workflow 让 6 service cov 跑进 CI —— 留
  `ci-integration-cov-matrix` 后续
- **NG5**: 不动前端或 docs

## Decisions

### D1: change name = `ci-coverage-all-services`

- **选择**: `ci-coverage-all-services`
- **理由**: 与 3 个 retrospective §4 共同引用名一致
- **已考虑 alternative**: `coverage-fail-under-propagate`(B),`coverage-matrix-v1-finalize`(C)

### D2: orchestrator change 不直接 apply

- **选择**: 本 change 只产出 6 sub-change scaffold,**不**直接改 prod
- **理由**:
  - 1-2 周 followup chain 在单 session 不可能
  - orchestrator 模式在 git history 清晰显示"原 change 拆分 followup 6 条"
- **已考虑 alternative**: 直接 apply(B),per-status 拆 2 change,1 mega-change

### D3: per-service 拆 6 sub-change

- **选择**: 6 sub-change 各自独立,顺序可调
- **理由**:
  - per-service 拆最干净,跟 `coverage-improvement` 同 pattern
  - 每个 sub-change 30-45 分钟 apply
  - 未来 audit 清晰
- **已考虑 alternative**: per-status 拆 2 change(B),1 mega-change

### D4: sub-change 命名约定

- **选择**: `ci-coverage-{service-name}` 格式
- **理由**:
  - 跟 `gateway-scanner-coverage-matrix` (前 1 个 change) 名字风格对齐
  - service 名字直白:`audit-isolation` / `gateway-scanner` /
    `workflow-engine` / `sso` / `mcp` / `credential`
- **已考虑 alternative**: `cov-{service}-100pct`(B),`{service}-cov-enforce`(C)

### D4a: scope 调整为 2 sub-change(apply Task 1 evidence)

- **选择**: 只 scaffold `ci-coverage-credential` + `ci-coverage-sso`,
  撤销原计划 6 sub-change 中的 4 个(audit-isolation / gateway-scanner /
  workflow-engine / mcp)
- **理由**:
  - apply Task 1.2 `grep addopts` 显示 **4 / 6 service 已设**
    `--cov-fail-under=100`:audit-and-isolation / gateway-scanner /
    workflow-engine / mcp
  - 只 credential + sso 2 个 service pyproject 用 `addopts = ["--strict-markers", ...]`
    list 形式,未设 fail-under
  - retrospective §4.1 估的"~3 commits, ~50 行 config" 实际只在
    credential + sso 需要
- **已考虑 alternative**:
  - 坚持 6 sub-change(4 trivial + 2 要改)—— 浪费 apply 时间
  - 重构为 4 trivial in scope —— 4 个已 done 的 service 无新 work

### D5: 6 sub-change apply 顺序建议

- **选择**: 建议顺序(非强制):
  1. `ci-coverage-gateway-scanner` (trivial, 1 commit, ~10 min)
  2. `ci-coverage-audit-isolation` (大, ~4 commits, ~2 hours)
  3. `ci-coverage-workflow-engine` (中, ~3 commits, ~1.5 hours)
  4. `ci-coverage-mcp` (小, ~2 commits, ~30 min)
  5. `ci-coverage-sso` (小, ~2 commits, ~30 min)
  6. `ci-coverage-credential` (最大, 需先修 15 errors, ~3 commits, ~2 hours)
- **理由**:
  - trivial 优先, 立即给 user 反馈
  - audit-isolation 最大但已有 4 module 100%(摸底较容易)
  - credential 最大因为有 pre-existing error
- **已考虑 alternative**: alphabetical 顺序,按 test count 排序

### D6: 6 sub-change 共用 6 artifact 模板

- **选择**: 6 sub-change 各自走 brainstorm / proposal / design / specs / tasks / plan
  / verify / retrospective 8 artifact,模板复用 3 个前 coverage change
- **理由**:
  - CLAUDE.md 强制所有 change 走 schemas
  - 模板复用降低写 markdown 时间
- **已考虑 alternative**: sub-change 简化为 4 artifact(违反 schema)

### D7: 跳过本地 design doc 走 openspec

- **选择**: 只写 `openspec/changes/ci-coverage-all-services/brainstorm.md`,
  不写 `docs/superpowers/specs/...`
- **理由**: 前 3 个 change 显式选 A
- **已考虑 alternative**: 双写

## Risks / Trade-offs

- **[Risk] R1**: 6 sub-change 链 1-2 周 followup,team 必须接受多 session apply
  → Mitigation: 本 change 给 followup 顺序 + 估计时间表,team 可分阶段 apply

- **[Risk] R2**: `credential` 15 errors 修不修是 sub-change 第一步决策
  → Mitigation: sub-change plan.md 第一步明确"跑 pytest 看 errors, surface
  给用户决策"

- **[Risk] R3**: `audit-and-isolation` 41 module 摸底范围最大
  → Mitigation: sub-change 摸底阶段用 grep 一次性扫 41 module 的 cov 起点
  + 排序按 missing 数量决定优先级

- **[Risk] R4**: 6 sub-change 各自 apply 期间可能有临时 broken state(加了
  fail-under 但 test 还没补)
  → Mitigation: sub-change 必须**先**补 test 达 100% **再**加 fail-under,
  不能反过来

- **[Trade-off] T1**: 6 sub-change 命名 `ci-coverage-{svc}` 跟现有
  `gateway-scanner-coverage-matrix` 风格略不一致(本 change 加 `ci-` 前缀)
  → 接受理由:`ci-` 前缀强调"CI enforcement" 跟 "100% line coverage" 区分

- **[Trade-off] T2**: 6 sub-change 各自走完整 8 artifact 流程,markdown ~10 KB
  / change,共 ~60 KB
  → 接受理由:CLAUDE.md 强制,模板复用率高

## Migration Plan

N/A — 本 change **不**涉及部署变更。

**具体说明**:
- 本 change 不改任何 prod code / pyproject / config
- 6 sub-change 各自 apply 才产生实际变更
- 6 sub-change apply 顺序见 D5

**部署顺序**(跨 1-2 周):
1. 本 change apply: 创建 6 sub-change scaffold + 写每个 sub-change 6 artifact
2. `ci-coverage-gateway-scanner` apply: trivial(加 fail-under)
3. `ci-coverage-audit-isolation` apply: 大, 摸 41 module 起点 + 补 test
4. `ci-coverage-workflow-engine` apply: 中, 摸 + 补
5. `ci-coverage-mcp` apply: 小
6. `ci-coverage-sso` apply: 小
7. `ci-coverage-credential` apply: 最大, 修 15 errors + 摸 + 补

**回滚策略**:
- 6 sub-change 各自可独立 `git revert <commit>`
- 无生产影响

**验收条件**:
- 6 sub-change scaffold 全部创建且 6 artifact 全部 done
- 6 sub-change 在 `openspec list` 可见,active 状态
- 本 change archive 落地

## Open Questions

**无**。
