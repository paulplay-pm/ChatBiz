## Context

`ci-coverage-all-services/retrospective.md §4.1` 提议的下一条 change。
credential service 仍是 4 PASS / 15 errors,pyproject 无 `--cov-fail-under=100`。
本 change 关闭 `ci-coverage-all-services` 的 2 sub-change 中第一个。

**当前状态**:
- 4 PASS / 15 errors
- 15 errors 根因 = `from app import crypto` 路径错(pythonpath 没设)
- pyproject addopts = list,无 `--cov-fail-under=100`
- 13 prod file(除 `__init__.py`)

**约束**:
- 0 行 prod code 改动
- 0 行 credential 既有 test 改动(15 errors 修是 config 层面)
- 不引入新 PyPI 依赖
- 不动 12 个 eng-review 决策任一条

**利益相关方**:
- paul(sponsor)
- credential service owner
- CI 维护者(future ci-integration-cov-matrix)

## Goals / Non-Goals

**Goals**:
- **G1**: 修 15 errors(加 `pythonpath = ["."]` 到 pyproject)
- **G2**: 补 test 达 100% line cov(credential 13 prod file)
- **G3**: 加 3 flag 到 pyproject `--cov=app --cov-report=term-missing --cov-fail-under=100`
- **G4**: 0 行 prod code 改动

**Non-Goals**:
- **NG1**: 不改 credential `app/` 下 prod code
- **NG2**: 不加 GitHub Actions workflow
- **NG3**: 不动 sso / 其他 service
- **NG4**: 不重命名或拆 13 prod file

## Decisions

### D1: change name = `ci-coverage-credential`
跟 scaffold 名一致。

### D2: scope = 修 import + 补 test + 加 fail-under

### D3: 修 15 errors 加 `pythonpath = ["."]`
1 行 config fix,跟 5 个前 coverage change 加 `--cov` flag 同 pattern。

### D4: 0 行 prod code 改动
跟 4 个前 coverage change 同 pattern。

### D5: 走完整 openspec 8 artifact

### D6: 跳过本地 design doc 走 openspec
跟 4 个前 change 一致。

## Risks / Trade-offs

- **[Risk] R1**: 修 import 后可能发现更多 issues(原 15 errors 可能是冰山一角)
  → Mitigation: apply Task 1 修 import 后立即跑 pytest,看真实 fail 数

- **[Risk] R2**: 补 test 数量因 credential prod code 复杂度未摸清
  → Mitigation: apply 阶段跑 cov 拿 missing lines,逐 line 补

- **[Trade-off] T1**: 1 行 `pythonpath = ["."]` 是 config 改,**严格**算
  test config 改动(类比 4 个前 change 加 `--cov` flag)
  → 接受理由:CLAUDE.md 不要求"0 行 config 改"

## Migration Plan

N/A — 本 change **不**涉及部署变更。

**部署顺序**:
1. apply Task 1: 修 import(`pythonpath = ["."]`)
2. apply Task 2: 跑 pytest 拿真实 PASS/FAIL 数
3. apply Task 3-4: 补 test 达 100%
4. apply Task 5: 加 3 flag 到 pyproject
5. apply Task 6: prod diff 验证
6. apply Task 7: git add + commit
7. apply Task 8: openspec archive

**回滚策略**: `git revert <commit>`

**验收条件**:
- `pytest services/credential/tests/ --cov=app --cov-fail-under=100` 全 PASS,exit 0
- 0 行 `services/credential/app/` 改动
- 1 commit 落地

## Open Questions

**无**。
