# Verification Report

**Change**: web-portal-shell
**Verified at**: 2026-06-13
**Verifier**: Claude Opus 4.8 (apply skill, controller-driven)

---

## 1. Structural Validation

- [x] `openspec validate web-portal-shell` → `Change 'web-portal-shell' is valid`
- [x] 7/8 artifacts complete (brainstorm / proposal / design / specs / tasks / plan / verify); retrospective pending (post-verify artifact)

## 2. Task Completion

- [x] `tasks.md` 26/26 items checked
- [x] Branch `worktree-web-portal-shell` ahead of main by **8 commits**, all V1 scoped to `web/portal/**` + `openspec/changes/web-portal-shell/**`
- [x] No drift into `web/canvas/**` / `web/admin/**` / `web/nginx.conf` / `web/Dockerfile` / `web/index.html` / `infrastructure/**` / `openspec/specs/<existing>/**` (verified via `git diff main..HEAD --name-only` — 57 files, all under the 2 allowed paths)

## 3. Build + Test

- [x] `pnpm --dir web/portal exec tsc --noEmit` → exit 0
- [x] `pnpm --dir web/portal exec vite build` → exit 0; `dist/index.html` (567 B) + `dist/assets/index-*.css` (10.59 kB) + `dist/assets/index-*.js` (201.39 kB)
- [x] `pnpm --dir web/portal exec vitest run` → 12 test files, 33/33 tests pass (Button 3, Card+MetricCard+StatusDot 3, Input 2, Modal+Toast 4, Sidebar 3, menu 4, RequireAuth 2, LoginPage 1, ComingSoonPage 3, DashboardPage 2, AppLayout 1, Router 5)
- [x] `pnpm --dir web/portal exec playwright test` → 2/2 e2e pass (login → dashboard → sidebar workflow; sidebar credential → coming-soon)

## 4. Spec Compliance (3 new spec files, 0 modified spec)

- [x] `specs/portal-shell/spec.md` — 5 Requirement: 登录页+localStorage / AppLayout / 30+ 侧栏菜单 / ComingSoonPage 单组件占位 / DashboardPage 4 metric + quick action / Vite+TS 严格 / Playwright e2e
- [x] `specs/design-tokens/spec.md` — 2 Requirement: tailwind.config.js 与 prototype 逐位一致 / glass 工具类 / Google Fonts
- [x] `specs/tailwind-primitive-library/spec.md` — 6 Requirement: Button / Card+MetricCard+StatusDot / Input+Form+Modal / Toast+useToast / Sidebar+Item+Section / RequireAuth
- [x] 0 modified spec — V1 doesn't touch `canvas-shell` / `canvas-auth` / any existing spec

## 5. Scope Check (V1 边界)

- [x] `web/canvas/**` 0 changes (`git diff main..HEAD --name-only | grep 'web/canvas/' | wc -l` = 0)
- [x] `web/admin/**` 0 changes
- [x] `web/nginx.conf` 0 changes
- [x] `web/Dockerfile` 0 changes
- [x] `web/index.html` 0 changes
- [x] `infrastructure/**` 0 changes
- [x] 既有 spec (`openspec/specs/<existing>/spec.md`) 0 changes
- [x] V1 introduces only `web/portal/**` (new) + `openspec/changes/web-portal-shell/**` (V1 artifacts)

## 6. Design Token Parity

- [x] `web/portal/tailwind.config.js` brand-50..900 hex values match `docs/prototype.html:20-27` exactly (10 brand colors: `#f0f4ff, #e0e9ff, #c2d4ff, #94b4ff, #5e8bff, #3b6ef5, #2a52d8, #2240b0, #1f368e, #1e3072`)
- [x] `web/portal/tailwind.config.js` ink-50..950 hex values match exactly (11 ink colors: `#f6f7f9, #eceef2, #d5d9e2, #b0b8c8, #8591a8, #66728a, #525b70, #444b5c, #3a3f4d, #1e2128, #0f1115`)
- [x] `web/portal/tailwind.config.js` font-sans = `['DM Sans', 'system-ui', 'sans-serif']`, font-mono = `['Space Mono', 'monospace']` — match `docs/prototype.html:11-14`
- [x] `web/portal/src/index.css` `.glass` utility + 5 `.status-*` classes + `@keyframes pulse` — match prototype
- [x] `web/portal/index.html` Google Fonts `<link>` with `DM+Sans:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap` — match
- [x] `openspec/changes/web-portal-shell/checklist/tailwind-config-parity.md` portal column 23 rows all `[x]` (canvas + admin columns remain `[ ]` for V2 / V3)

## 7. Browser Manual (Optional — V1 standalone dev 5174)

V1 is configured to run as a standalone Vite dev server on port 5174 (independent of nginx 5173 integration, which is V2's job). Manual browser verification was not performed in this session due to the 2/2 playwright e2e covering the critical paths:

- login → localStorage write + redirect to `/portal/`
- dashboard renders inside `AppLayout` with 30+ sidebar items across 5 sections
- click "凭证管理" (sidebar-item-credential) → `/portal/coming-soon?from=credential` → page shows "「凭证管理」将由 V1.0+ 接入"

## 8. Forced Additions (3 accepted deviations from "EXACT templates")

All 3 are minimal, correct, and forced by gaps in the plan's templates:

1. **Plan Task 2**: Added `@types/node` to `package.json` devDeps + `"node"` to `tsconfig.json` `types` array. Required because `vitest.config.ts` uses `path` and `__dirname` (Node.js APIs).
2. **Plan Task 2**: Added `passWithNoTests: true` to `vitest.config.ts`. Required because vitest 1.6 exits 1 on "No test files found" by default; V1 must exit 0 with 0 specs at scaffold time.
3. **Plan Task 2**: Created `web/portal/.gitignore` (not in plan's file list). Required because root `.gitignore` doesn't cover `web/portal/node_modules/`, and `git add web/portal/` would otherwise stage 3000+ node_modules files.
4. **Plan Task 3**: MENU extended from 22 items to 30 items. Required because the plan's `menu.test.ts` asserts `>= 30` while the plan's `MENU` data had only 22. Added 8 items from `docs/prototype.html` to satisfy the spec's `30+ items` Requirement.
5. **Plan Task 3**: Toast test `beforeEach`/`afterEach` callbacks wrapped in block bodies. Required to avoid TS error on `vi.useFakeTimers()` return-type assignment under vitest 1.6.1.
6. **Plan Task 4**: Added `?? ''` fallback in `router/index.tsx` `useActiveId` to satisfy `noUncheckedIndexedAccess: true` strict-mode TS rule. Pure type-narrowing, no behavioral difference (MENU hrefs are never empty).
7. **Plan Task 5**: e2e spec URLs updated to use `/portal/`-prefixed paths and `data-testid="coming-soon"` scoping. Required because Vite's `base: '/portal/'` serves routes at `/portal/...`, not `/...` (plan's templates assumed no base). Second fix scoped the "凭证" text query to avoid matching both sidebar item and body content.

## 9. OpenSpec CLI Final State

```text
openspec status --change web-portal-shell
[x] brainstorm
[x] proposal
[x] design
[x] specs
[x] tasks
[x] plan
[-] verify (in progress)
[ ] retrospective (blocked by: verify)
```

After this verify.md is written, run `openspec-archive-change` to sync the 3 new spec files into `openspec/specs/portal-shell/` + `openspec/specs/design-tokens/` + `openspec/specs/tailwind-primitive-library/` and move the change folder to `openspec/changes/archive/`.

## 10. V2 / V3 Handoff (Future Changes)

- **V2 (canvas-refactor)**: `web/canvas/tailwind.config.js` MUST match portal byte-for-byte; import portal primitives via cross-sub-app Vite alias; modify `specs/canvas-shell/spec.md` (顶部栏 + 错误边界 两个 Requirement); integrate nginx 5173.
- **V3 (admin-refactor)**: `web/admin/tailwind.config.js` MUST match portal byte-for-byte; integrate nginx 5173.
- **V2 + V3 together**: `web/nginx.conf` + `web/Dockerfile` 增量 + `web/README.md` 统一三套子应用说明.
- **Integration test (V3+)**: portal ↔ canvas ↔ admin 5173.

V1 is intentionally scoped as the smallest viable portal deliverable to unblock V2 and V3 without scope creep.
