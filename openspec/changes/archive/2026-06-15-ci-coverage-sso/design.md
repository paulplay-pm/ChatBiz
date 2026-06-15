## Context

`ci-coverage-all-services/retrospective §4.1` 提议 2 sub-change 中第 2 个:
sso service。本 change 关闭 ci-coverage-all-services 整个 orchestrator
chain。

**当前状态**:
- 3 fail / 1 skip / 4 errors(全是 `from app import` 路径错)
- 16 prod file
- pyproject addopts list, 无 `--cov-fail-under`, 无 `pythonpath`

**约束**:
- 0 行 prod code 改动
- 不引入新 PyPI 依赖(假设 dev deps 已装)
- 不动 12 个 eng-review 决策任一条

## Goals / Non-Goals

**Goals**:
- **G1**: 修 4 errors(加 `pythonpath = ["."]` 到 pyproject)
- **G2**: 摸 15 prod file 起点 + 补 8 module 100% test + 接受 4 module partial
  (followup scope,详见 `retrospective.md §4.1`)
- **G3**: 加 3 flag 到 pyproject
- **G4**: 0 行 prod code 改动

**Non-Goals**:
- **NG1**: 不改 `sso/app/` 下 prod code
- **NG2**: 不加 CI workflow
- **NG3**: 不修 pre-existing V6a mock 兼容问题(1 skip 接受)

## Decisions

### D1-D6: 跟 ci-coverage-credential 完全同 pattern

(参考 ci-coverage-credential/retrospective.md §5 模板复用)

## Risks / Trade-offs

- **[Risk] R1**: 修 import 后可能仍 fail(test code 真实 fail vs 路径问题)
  → Mitigation: 跑 pytest 拿真实 fail 数,逐个 surface

- **[Trade-off] T1**: 1 SKIP (V6a) 接受
  → 接受理由:本 change scope 外

## Migration Plan

N/A.

**部署顺序**:
1. 加 `pythonpath = ["."]` 到 pyproject
2. 跑 pytest 摸底
3. 补 test 达 100%
4. 加 3 flag
5. prod diff 验证
6. git add + commit
7. openspec archive

**验收条件**:
- `pytest --cov=app --cov-fail-under=100` 全 PASS(1 skip 接受),exit 0
- 0 行 `services/sso/app/` 改动
- 1 commit 落地

## Open Questions

**无**。
