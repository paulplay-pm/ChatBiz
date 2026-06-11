# fix-canvas-real-tests Implementation Plan

**Goal:** 让真实测试命令闭环:backend focused smoke、frontend vitest/typecheck/build/playwright 全部可跑且可解释。

## Phase 1: Playwright e2e

1. 创建 `web/canvas/e2e/auth.spec.ts`:
   - mock `/api/auth/login`
   - 打开 `/login`
   - 填 username/password
   - 点击登录
   - 断言 URL 包含 `/workflows`

2. 创建 `web/canvas/e2e/canvas-drag-loop.spec.ts`:
   - 走登录
   - mock `/workflows`
   - 进入 `/workflows/mock/edit`
   - 断言画布 shell / 节点面板 / 保存按钮可见

3. 创建 `web/canvas/e2e/paul-monthly-report.spec.ts`:
   - mock workflow-engine APIs
   - 创建/进入 workflow
   - mock SSE 响应
   - 断言运行路径可触达

## Phase 2: Real commands

Run:
```bash
cd web/canvas
pnpm install
npx vitest run
pnpm typecheck
pnpm build
npx playwright install chromium
npx playwright test
```

Backend:
```bash
cd services/workflow-engine
conda run -n chatbiz python -m pytest tests/test_auth_upgrade.py tests/e2e/test_manual_approval.py tests/security/test_cross_user.py tests/security/test_credential_check.py -q --tb=short --disable-warnings --no-cov
```

## Phase 3: verify

Update `web/canvas/verify.py` to require 3 e2e specs.

Write verify.md with exact command outputs.

## Phase 4: archive

Mark tasks complete, write retrospective, archive.
