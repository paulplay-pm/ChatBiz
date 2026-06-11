## Context

本 change 修复 `implement-canvas-ui` archive 后真实测试闭环不足的问题。当前实测:

- `pnpm install` 成功(使用 npmmirror)
- `npx vitest run` 已经可通过 13/13
- `pnpm typecheck` 已经可通过 0 errors
- `pnpm build` 已成功,仅 bundle size warning
- `npx playwright test` 失败:No tests found
- 后端 focused pytest 在 conda chatbiz 环境中 13/13 通过(`--no-cov`),但 coverage gate 100% 失败(当前约 57%)

## Goals / Non-Goals

**Goals:**
- 补 Playwright e2e specs,让 `npx playwright test` 真实执行并通过。
- 更新 `web/canvas/verify.py` 检查真实 e2e spec 文件。
- 补若干 workflow-engine 纯函数/API tests，提高 coverage 并明确剩余 coverage gap。
- 记录真实测试命令和结果。

**Non-Goals:**
- 不扩展产品功能。
- 不降低 100% coverage 标准。
- 不一次性强行补完 workflow-engine 所有 100% coverage(除非工作量可控)。

## Decisions

### D1: Playwright 用 mock route 而不依赖真实后端
- **选择**: `page.route()` mock `/api/auth/login`、`/workflows`、`/api/nodes/*`、`/runs/*`。
- **理由**: e2e 关注 UI 交互路径，真实后端已由 pytest 覆盖；mock 保证稳定。

### D2: 后端 smoke 与 coverage 分开
- **选择**: focused smoke 用 `--no-cov`，coverage 单独跑并作为 gap 报告。
- **理由**: 真实业务路径是否通过和 coverage 是否达 100% 是两个不同 gate，不能混淆。

### D3: verify.py 检查真实测试文件
- **选择**: `verify.py` 必须检查 `e2e/*.spec.ts` 至少 3 个，而不只检查 `playwright.config.ts`。
- **理由**: 避免再次出现 No tests found。

## Risks / Trade-offs

- **Risk**: Playwright 浏览器未安装 → Mitigation: `npx playwright install chromium`。
- **Risk**: mock route 与真实 API drift → Mitigation: mock payload 结构从现有 workflow-engine API response 抽取。
- **Trade-off**: focused smoke `--no-cov` 仍不能证明 100% coverage → 接受,但必须在 verify/retro 中记录为 blocking follow-up 或继续补测。

## Migration Plan

1. 添加 Playwright specs。
2. 跑 `npx playwright install chromium`(如必要)。
3. 跑前端 4 个真实命令。
4. 跑后端 conda focused smoke。
5. 更新 verify.py 和文档。
6. 提交。

## Open Questions

无。