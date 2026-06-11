# brainstorm: fix-canvas-real-tests

## 背景

`implement-canvas-ui` 已 merge + archive 后，真实环境测试暴露 4 类未闭环项:

1. `pnpm install` 后，`npx vitest run` 最初失败，已修到 13/13 通过。
2. `pnpm typecheck` 最初失败，已修到 0 errors。
3. `pnpm build` 已成功，但有 bundle size warning(非阻塞)。
4. `npx playwright test` 目前显示 `No tests found`，因为 `web/canvas/e2e/` 只有目录和 config，没有 `.spec.ts`。
5. 后端 focused pytest 已在 conda `chatbiz` 环境跑通 13 tests，但默认 coverage gate 100% 会失败，当前覆盖率约 57%。

目标不是扩功能，而是补齐“真实测试全部绿”的最小闭环。

## 决策

### Q1: 后端 100% coverage 怎么处理?

**选择**: 本修复 change 不降低 coverage 门槛，而是补最关键的单元测试以尽量提升覆盖；若 100% 在本次范围内代价过高，verify 明确列为 blocking gap 并给出下一步。

理由: CLAUDE.md / openspec 配置要求单元 ≥100%，不应静默降低。但 workflow-engine 是 1300+ 行代码，当前 57%，一次小修复内补到 100% 可能需要 50+ 测试。先补 API/graph/nodes/clients 的主要纯函数。

### Q2: Playwright 怎么补?

**选择**: 增加 3 个最小 e2e:
- `auth.spec.ts`: 打开 /login,填写用户名,进入 /workflows
- `canvas-drag-loop.spec.ts`: 访问画布页，验证页面可渲染画布 shell
- `paul-monthly-report.spec.ts`: mock 后端 API + SSE，验证可创建 workflow / 进入画布 / 运行按钮路径

理由: 当前 e2e 是 0，至少要有 smoke 覆盖真实 Playwright runner。

### Q3: 真实 test command 标准是什么?

**选择**:
- 前端: `pnpm install`, `pnpm typecheck`, `pnpm build`, `npx vitest run`, `npx playwright test`
- 后端: `conda run -n chatbiz python -m pytest tests/test_auth_upgrade.py tests/e2e/test_manual_approval.py tests/security/test_cross_user.py tests/security/test_credential_check.py --no-cov` 作为 focused smoke；coverage 另跑并记录。

## Non-goals

- 不扩展 canvas 功能
- 不重写架构
- 不把 workflow-engine 全量测试强行一次补到 100%（除非局部补测足够）
- 不引入真实浏览器后端服务依赖，Playwright 使用 mock route

## Open Questions

无。