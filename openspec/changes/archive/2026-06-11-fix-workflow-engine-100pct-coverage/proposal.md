## Why

`fix-canvas-real-tests` 已确认 workflow-engine focused smoke 13/13 通过,但默认 `--cov-fail-under=100` 仍失败,当前 57% coverage。CLAUDE.md 锁定 100% 单元覆盖率,本 follow-up 必须补到 100% 才能默认开启 coverage gate。

## What Changes

- 在 `services/workflow-engine/tests/` 大量补单元测试。
- 不动产品代码;只在 `app/errors/middleware.py` 等已 79-86% 的地方补 1-2 个小分支。
- 不降低 coverage 阈值。

## Capabilities

### New Capabilities
- `workflow-engine-unit-test-coverage`: workflow-engine 100% 单元覆盖率。

### Modified Capabilities
- `workflow-engine`: 内部测试结构(no spec-level change)。
- `llm-egress-gateway`: 间接(workflow-engine 是 PII detector consumer,不变)。

## Impact

- 影响 `services/workflow-engine/tests/` 添加 ~30-40 单元测试。
- 不改生产代码。
- CI: 启用 `python -m pytest tests/ --cov-fail-under=100`。
