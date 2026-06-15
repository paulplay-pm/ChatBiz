## Why

`ci-coverage-all-services/retrospective.md §4.1` 提议的下一条 change:

> | `ci-coverage-credential` |
> | scope: 跑 `pytest services/credential/tests/` 拿 15 errors 完整
>   traceback + 修 setup + 摸 18 prod file 起点 + 补 test + 加
>   `--cov=app --cov-report=term-missing --cov-fail-under=100` 到
>   pyproject |
> | estimated effort: ~2 hours |

紧接 `ci-coverage-all-services` (a17241e) push 后,2 个 sub-change
中处理 credential。**注意**: 摸底修正 retrospective §4.1 估的"18 prod
file"——实际 13 个(除 `__init__.py`)。

**apply Task 1 evidence 修 retrospective §4.1 推断**:
- 15 errors 根因 = `from app import crypto` 路径错(pythonpath 没设)
- **不**是 setup / env / db fixture 错
- 1 行 `pythonpath = ["."]` 加到 pyproject 修 15 errors

**源参考**:
- 触发源:`ci-coverage-all-services/retrospective.md §4.1`
- 模板:4 个前 coverage change 6 artifact 模板

## What Changes

**新增 capability: `ci-coverage-credential`**

- From: `services/credential/` 4 PASS / 15 errors,pyproject 无 `--cov-fail-under`
- To: `services/credential/` 全 PASS,~13 prod file 100% line cov,pyproject
  加 3 flag(`--cov=app` + `--cov-report=term-missing` + `--cov-fail-under=100`)
- Reason: 关闭 `ci-coverage-all-services/retrospective §4.1`
- Impact: **non-breaking**(修 test 路径 + 加 config,不动 prod code)

**1 行 pyproject config 改**(test config,不算 prod):
```diff
[tool.pytest.ini_options]
addopts = [
    "--strict-markers",
+   "--cov=app",
+   "--cov-report=term-missing",
+   "--cov-fail-under=100",
    ...
]
+pythonpath = ["."]
```

## Capabilities

### New Capabilities
- `ci-coverage-credential`: 让 `services/credential/app/` 13 个 prod file
  通过 pytest 单元测试达到 100% line coverage,加 `--cov-fail-under=100`
  到 pyproject 让 cov 数字 enforce。

### Modified Capabilities
无。

## Impact

**受影响的代码**:
- 改:`services/credential/pyproject.toml`(加 3 flag + `pythonpath`)
- 新增:`services/credential/tests/` 下可能若干新 test 函数

**前端范围 / 后端范围 / 是否豁免前端**:
- 后端范围:是(credential 是 Python FastAPI service)
- 前端范围:否
- **豁免前端**:credential 无前端组件

**API / DB / 协议层影响**:无。

**依赖**:无新增 PyPI 依赖。

**CI 集成**: 加 fail-under 后,本地 `pytest` 跑会 enforce。CI workflow 改造
留 `ci-integration-cov-matrix`。

## Non-goals

- **NG1**: 不改 credential `app/` 下 prod code —— 0 行改动
- **NG2**: 不加 GitHub Actions workflow —— 留 `ci-integration-cov-matrix`
- **NG3**: 不修 15 errors 之外的 setup 问题(原 4 PASS unit test 是预期)
- **NG4**: 不重命名或拆 13 prod file
- **NG5**: 不动 `services/credential/cron.py` 之外 cron 任务

## Future-Implementation 标注检查

本 change **不**触及 API/DB/前端契约,**不**适用 `[FUTURE-IMPLEMENTATION]` tag。

## eng-review 冲突检查

本 change **不**触及设计 doc "## GSTACK REVIEW REPORT" 中 12 个锁定决策任一条。
