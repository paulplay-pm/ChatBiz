# canvas-tsc-health — Proposal

## Why

`web/canvas` 的 `pnpm build` 脚本是 `tsc --noEmit && vite build`，目前 `tsc --noEmit` 报 **16 个 error**（不是 warning）。在 `web-integration-test-suite` change 里只能绕过（`Makefile` 直接调 `vite build`），但这意味着 production `web/Dockerfile` 也**永远构建失败**——跟测试 infra 无关，pure production CI/CD 就卡在这。

16 个 error 分 3 类：
- **bug**：`src/main.tsx:20` — `Property 'env' does not exist on type 'ImportMeta'`  
  缺少 `/// <reference types="vite/client" />`（vite 三斜线指令），**Vite 容器内构建必 fail**（admin-bootstrap retrospective §2 已经把 `src/vite-env.d.ts` 加到了 admin 项目，canvas 当时漏了
- **预存未使用变量/import**：3 个文件各 1 个（`vi`、`React`、`'afterEach'`）
- **Playwright `Element | undefined` null-check 缺失**：2 个 e2e spec（`canvas-connection.spec.ts` + `canvas-edge-deletion.spec.ts`）在 `page.locator()` 后没做非空断言

不改：production Dockerfile 的 `tsc --noEmit` 永远报错→`web` 容器 build 失败；任何新前端开发者 `pnpm build` 跑不通。

改：本 change 修 6 个文件（3 bug 类 + 3 预存 clean-up 类），修完后 `pnpm build`（含 `tsc --noEmit && vite build`）退出码 0。

参考基线：
- `web/admin-bootstrap` retrospective §2 "TS 不认 CSS side-effect import — 加 `src/vite-env.d.ts`"
- `web/admin/src/vite-env.d.ts`（已有，admin 项目加了，canvas 漏了）

## What Changes

- **新增** `web/canvas/src/vite-env.d.ts`，含 `/// <reference types="vite/client" />`（修 `ImportMeta.env` 报错）
- **修改** `e2e/canvas-connection.spec.ts`：`page.locator(...)` 返回类型 `Element | undefined` → 加 non-null assertion `!` 或 `expect(...).toBeDefined()`（9 处）
- **修改** `e2e/canvas-edge-deletion.spec.ts`：同上（7 处）
- **修改** `tests/components_chatflow.test.tsx`：删未使用 import `vi`
- **修改** `tests/components_layout.test.tsx`：删未使用 import `React`
- **修改** `tests/hooks_useSession.test.ts`：删未使用 import `afterEach`
- **修改** `tests/hooks_useSaveWorkflow.test.ts`：`getState()` call missing arg → 加空对象 `{}`

**不** 改：
- `pnpm dev` / `pnpm test` 的既有流程
- 任何业务逻辑
- `web/admin/` 或 `services/` 的任何文件

## Capabilities

### Modified Capabilities

- `canvas-shell`：type-safe 构建 capability。**前端范围** = `web/canvas/src/vite-env.d.ts`（新）+ 5 个既有文件的类型修复。**后端范围** = N/A。

## Impact

- **代码层**：`web/canvas/src/vite-env.d.ts`（新）+ 6 个既有文件改动（1 新增 + 5 修复 + 1 修正调用）
- **依赖**：无新增
- **openspec/config.yaml §apply.rules**：不触发（纯前端 type fix，不动 compose/API）

## Non-goals

- **不** 做 `pnpm dev` / `pnpm test` / `pnpm e2e` 的改动
- **不** 做 `web/admin` 的任何改动（admin 已有 `vite-env.d.ts`）
- **不** 引入 ESLint（后续 change）
- **不** 修 canv 业务代码的任何行为 bug
