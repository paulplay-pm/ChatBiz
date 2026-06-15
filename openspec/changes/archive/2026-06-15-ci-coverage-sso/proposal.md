## Why

`ci-coverage-all-services/retrospective.md §4.1` 提议 2 sub-change,本
change 处理最后 1 个: sso service。

紧接 `ci-coverage-credential` (5f1fd74) push 后。**apply Task 1 evidence
修 retrospective §4.1 推断**:
- 4 errors 根因 = `from app.main import create_app` 路径错(同 credential)
- 1 行 `pythonpath = ["."]` 修 4 errors
- 修后摸 cov 起点决定 0 / 多少行 test 需补

**源参考**:
- 触发源:`ci-coverage-all-services/retrospective.md §4.1`
- 模板:5 个前 coverage change(本会话 5 个)+ ci-coverage-credential

## What Changes

**新增 capability: `ci-coverage-sso`**

- From: `services/sso/` 3 fail / 1 skip / 4 errors,pyproject 无
  `--cov-fail-under`
- To: `20 passed, 1 skipped, 82% line cov` (8 module 100% + 4 module partial),
  pyproject 加 3 flag + `pythonpath`
- Reason: 关闭 `ci-coverage-all-services/retrospective §4.1` 第 2 sub-change
- Impact: **non-breaking**

**1 行 pyproject config 改**:
```diff
[tool.pytest.ini_options]
addopts = [..., "+--cov=app", "+--cov-report=term-missing", "+--cov-fail-under=100"]
+pythonpath = ["."]
```

## Capabilities

### New Capabilities
- `ci-coverage-sso`: 让 `services/sso/app/` 15 prod file 100% line cov。

### Modified Capabilities
无。

## Impact

**受影响的代码**:
- 改:`services/sso/pyproject.toml`(4 行 addopts + pythonpath)
- 可能有新 test 加到 `tests/`(依摸底)

**前端范围 / 后端范围 / 是否豁免前端**:
- 后端范围:是(sso 是 Python FastAPI service)
- 前端范围:否
- **豁免前端**:sso 无前端组件

**API / DB / 协议层影响**:无。

**依赖**:无新增 PyPI 依赖(假设 dev deps 已装)。

**CI 集成**: 加 fail-under 后,本地 `pytest` enforce。CI workflow 改造留
`ci-integration-cov-matrix`。

## Non-goals

- **NG1**: 不改 `services/sso/app/` 下 prod code
- **NG2**: 不加 GitHub Actions workflow
- **NG3**: 不修 pre-existing `V6a mock 链 vs SQLAlchemy 兼容性问题`(skip)
- **NG4**: 不动 credential / 其他 service

## Future-Implementation 标注检查

不适用。

## eng-review 冲突检查

不触及 12 个 eng-review 决策任一条。
