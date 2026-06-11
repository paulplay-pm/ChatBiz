# tasks: fix-canvas-real-tests

## 1. Canvas Playwright e2e

- [x] 1.1 写 `web/canvas/e2e/auth.spec.ts`
- [x] 1.2 写 `web/canvas/e2e/canvas-drag-loop.spec.ts`
- [x] 1.3 写 `web/canvas/e2e/paul-monthly-report.spec.ts`
- [x] 1.4 运行 `npx playwright install chromium`(若需要)
- [x] 1.5 运行 `npx playwright test` 并修到通过

## 2. Canvas existing gates

- [x] 2.1 运行 `npx vitest run` 并确保 13+ tests passed
- [x] 2.2 运行 `pnpm typecheck` 并确保 0 errors
- [x] 2.3 运行 `pnpm build` 并确保退出码 0
- [x] 2.4 更新 `web/canvas/verify.py` 检查 3 个 e2e spec 文件

## 3. workflow-engine smoke

- [x] 3.1 运行 conda chatbiz focused smoke 13 tests
- [x] 3.2 记录 coverage gate 当前状态
- [x] 3.3 如有低成本后端测试补充,补上

## 4. verify / retro / archive

- [x] 4.1 写 verify.md
- [x] 4.2 写 retrospective.md
- [x] 4.3 archive change
- [x] 4.4 merge/cleanup
