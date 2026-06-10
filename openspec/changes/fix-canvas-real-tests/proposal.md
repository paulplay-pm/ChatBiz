## Why

`implement-canvas-ui` 的代码已合入 main，但真实依赖安装后发现测试闭环不完整:Vitest/typecheck/build 已可跑，Playwright 没有任何 spec，后端 pytest 需要 `--no-cov` 才能通过 focused smoke，coverage gate 仍失败。这个 change 专门补齐真实测试命令和最小 e2e，避免把“verify.py 文件存在检查”误当成“测试真的通过”。

## What Changes

- 新增 canvas Playwright e2e specs，确保 `npx playwright test` 不再 `No tests found`。
- 修复/补充前端测试 setup，保证 `npx vitest run`、`pnpm typecheck`、`pnpm build` 真实通过。
- 补充 workflow-engine 关键单元/接口测试，记录 coverage gap，不降低 100% coverage 标准。
- 更新 `web/canvas/verify.py`，使其检查真实 e2e spec 文件，而不是只检查 playwright config。

## Capabilities

### New Capabilities
- `canvas-real-test-gates`: canvas-ui 的真实 test/typecheck/build/e2e gate。
- `workflow-engine-real-test-smoke`: workflow-engine 的 conda `chatbiz` 环境 focused smoke gate。

### Modified Capabilities
- `canvas-shell`: 增加真实 Playwright e2e gate 要求。
- `canvas-editor`: 增加 drag-loop / canvas page smoke e2e。
- `canvas-auth`: 增加 login e2e。

## Impact

- 影响 `web/canvas/e2e/`、`web/canvas/verify.py`、少量测试配置。
- 可能新增 `services/workflow-engine/tests/unit/` 纯函数测试。
- 不改产品功能路径。
