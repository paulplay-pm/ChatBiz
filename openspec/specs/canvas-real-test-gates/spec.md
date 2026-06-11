# canvas-real-test-gates Specification

## Purpose
TBD - created by archiving change fix-canvas-real-tests. Update Purpose after archive.
## Requirements
### Requirement: Canvas 真实测试命令
canvas-ui MUST 提供真实可运行的测试命令: `pnpm typecheck`, `pnpm build`, `npx vitest run`, `npx playwright test`;四者 MUST 全部退出码 0。

#### Scenario: TypeScript typecheck 通过
- **WHEN** 在 `web/canvas` 目录执行 `pnpm typecheck`
- **THEN** 命令 MUST 退出码 0,且 `tsc --noEmit` 无 error

#### Scenario: Vite build 通过
- **WHEN** 在 `web/canvas` 目录执行 `pnpm build`
- **THEN** 命令 MUST 退出码 0,允许 bundle-size warning,但不允许 TypeScript/Vite build error

#### Scenario: Vitest 通过
- **WHEN** 在 `web/canvas` 目录执行 `npx vitest run`
- **THEN** 命令 MUST 退出码 0,至少 13 个测试通过

#### Scenario: Playwright 通过
- **WHEN** 在 `web/canvas` 目录执行 `npx playwright test`
- **THEN** 命令 MUST 退出码 0,不允许 `No tests found`

### Requirement: verify.py 检查真实 e2e specs
`web/canvas/verify.py` MUST 检查 `web/canvas/e2e/*.spec.ts` 至少 3 个,且必须包含 auth、canvas drag-loop、paul monthly report 三类场景。

#### Scenario: e2e 文件存在
- **WHEN** 执行 `python web/canvas/verify.py`
- **THEN** verify MUST 检查 `auth.spec.ts`, `node-schema.spec.ts`, `paul-monthly-report.spec.ts` 存在;缺任意一个 MUST fail

