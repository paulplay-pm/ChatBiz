## 1. Worktree + 基线

- [x] 1.1 创建 worktree: `git worktree add .worktrees/web-portal-shell -b worktree-web-portal-shell` + 验证 `git status` 干净
- [x] 1.2 在 worktree 内,跑 `openspec validate web-portal-shell` 确认 4 个 artifacts 通过(brainstorm + proposal + design + 3 个新 spec) — 验证:命令 exit 0
- [x] 1.3 创建 `openspec/changes/web-portal-shell/checklist/tailwind-config-parity.md` checklist 模板(V1 仅 portal 1 份,V2 / V3 集成时复用)

## 2. portal 子应用脚手架

- [x] 2.1 创建 `web/portal/package.json`(react 18 + react-dom + react-router-dom 6 + tailwindcss 3.4 + postcss + autoprefixer + typescript 5.4 + vite 5 + @tanstack/react-query 5 + vitest 1 + @testing-library/react 16 + @testing-library/jest-dom + @testing-library/user-event + @playwright/test 1 + jsdom 24) — 验证:`pnpm --dir web/portal install` exit 0
- [x] 2.2 创建 `web/portal/tsconfig.json`(`strict: true` + `noUncheckedIndexedAccess: true` + `noImplicitAny: true` + `noUnusedLocals: true` + `noUnusedParameters: true` + `paths: { "@/*": ["src/*"] }`) — 验证:`pnpm --dir web/portal exec tsc --noEmit` 跑通(空 src)
- [x] 2.3 创建 `web/portal/tailwind.config.js`(prototype 完整 brand/ink 调色板 + DM Sans + Space Mono) — 验证:与 `docs/prototype.html:7-40` 头部的 `tailwind.config` 块逐位一致
- [x] 2.4 创建 `web/portal/postcss.config.js` + `web/portal/index.html` + `web/portal/vite.config.ts`(`base: '/portal/'` + dev port 5174) — 验证:`pnpm --dir web/portal exec vite build` exit 0,产物在 `web/portal/dist/`
- [x] 2.5 创建 `web/portal/src/main.tsx` + `web/portal/src/App.tsx` + `web/portal/src/index.css`(ReactDOM + QueryClientProvider + BrowserRouter basename='/portal' + ToastProvider + `.glass` 工具类 + Google Fonts 引入) — 验证:`tsc --noEmit && vite build` 跑通,产物含 `<div id="root">` + `<script type="module" src="/assets/index-*.js">`
- [x] 2.6 创建 `web/portal/src/vite-env.d.ts`(`/// <reference types="vite/client" />`) — 验证:`tsc --noEmit` 跑通
- [x] 2.7 创建 `web/portal/vitest.config.ts` + `web/portal/playwright.config.ts` — 验证:`pnpm --dir web/portal exec vitest run` 跑通(空 spec)+ `pnpm --dir web/portal exec playwright --version` 报版本

## 3. portal Primitives 原语库

- [x] 3.1 创建 `web/portal/src/components/primitives/Button.tsx`(variant: primary/secondary/ghost;size: sm/md/lg;`data-testid="btn"`) — 验证:`vitest Button.test.tsx` 3 个 case(primary variant / ghost variant / onClick)通过
- [x] 3.2 创建 `web/portal/src/components/primitives/Card.tsx` + `MetricCard.tsx` + `StatusDot.tsx` + `web/portal/src/index.css` 追加 `.status-running/success/error/idle/pending` 类 — 验证:`vitest Card/MetricCard/StatusDot.test.tsx` 5 个 case 通过
- [x] 3.3 创建 `web/portal/src/components/primitives/Input.tsx` + `Form.tsx` + `Modal.tsx`(`data-testid="modal"` + `data-testid="modal-backdrop"`) — 验证:`vitest Input.test.tsx` 2 个 case + `Modal.test.tsx` 2 个 case(open/close + backdrop click)通过
- [x] 3.4 创建 `web/portal/src/components/primitives/Toast.tsx` + `useToast.ts` hook(security/user/info 三色 + 5s 自动消失 + z-index 9999) — 验证:`vitest Toast.test.tsx` 4 个 case 通过
- [x] 3.5 创建 `web/portal/src/data/menu.ts`(5 sections + 30+ items,type `MenuItem` / `MenuSection` / `MenuStatus`) — 验证:`vitest menu.test.ts` 5 section + 30+ item + status 二选一通过
- [x] 3.6 创建 `web/portal/src/components/primitives/SidebarItem.tsx` + `SidebarSection.tsx` — 验证:`vitest SidebarItem.test.tsx` 2 个 case(active / hover)通过
- [x] 3.7 创建 `web/portal/src/components/primitives/Sidebar.tsx` — 验证:`vitest Sidebar.test.tsx` 3 个 case(5 section 渲染 / 30+ item 渲染 / active 高亮)通过
- [x] 3.8 创建 `web/portal/src/components/RequireAuth.tsx`(读 `localStorage['chatbiz.auth']`,未登录跳 `/login`) — 验证:`vitest RequireAuth.test.tsx` 2 个 case(已登录 / 未登录)通过

## 4. portal 主框架页面

- [x] 4.1 创建 `web/portal/src/pages/LoginPage.tsx`(username 任意非空 + 任意密码 + 提交写 `localStorage['chatbiz.auth']` + 跳 `/portal/`) — 验证:`vitest LoginPage.test.tsx` 1 个 case(提交后 localStorage 含 chatbiz.auth)通过
- [x] 4.2 创建 `web/portal/src/components/AppLayout.tsx`(固定顶部 glass header + 左侧 Sidebar + 右侧 `<Outlet/>` + sidebar 点击调 `onSelect`) — 验证:`vitest AppLayout.test.tsx` 3 个 slot 渲染通过
- [x] 4.3 创建 `web/portal/src/pages/ComingSoonPage.tsx`(读 `useSearchParams` 拿 `from` query + 查 MENU 渲染 label) — 验证:`vitest ComingSoonPage.test.tsx` 3 个 case(from 已知 / from 未知 / 无 from)通过
- [x] 4.4 创建 `web/portal/src/pages/DashboardPage.tsx`(4 个 MetricCard + 1 个 quick action 按钮) — 验证:`vitest DashboardPage.test.tsx` 2 个 case(4 metric / 1 quick action)通过
- [x] 4.5 创建 `web/portal/src/router/index.tsx`(React Router 6 + `/login` + `/` + `/coming-soon` + 通配 fallback) — 验证:`vitest router.test.tsx` 5 个 route resolve 正确通过
- [x] 4.6 修改 `web/portal/src/App.tsx` 使用 `PortalRouter`(替换占位) — 验证:`tsc --noEmit && vite build` 跑通

## 5. portal e2e + 文档

- [x] 5.1 创建 `web/portal/e2e/portal-flow.spec.ts` 第 1 个 spec:login → dashboard → sidebar workflow → `/canvas/workflows` — 验证:`playwright test` 第 1 个 spec PASS
- [x] 5.2 在 `web/portal/e2e/portal-flow.spec.ts` 加第 2 个 spec:sidebar credential → `/portal/coming-soon?from=credential` 渲染菜单名 — 验证:`playwright test` 第 2 个 spec PASS
- [x] 5.3 创建 `web/portal/README.md`(dev 5174 + build + e2e 命令;V1 期间独立 dev,V2 集成 nginx 5173) — 验证:`README.md` 含 3 个命令示例
- [x] 5.4 在 checklist 标记 portal 已对齐 prototype(checklist 1 行 ✓) — 验证:checklist 1 行 `[x]`,其余 `[ ]`

## 6. 端到端验证

- [x] 6.1 `pnpm --dir web/portal exec tsc --noEmit && pnpm --dir web/portal exec vite build && pnpm --dir web/portal exec vitest run && pnpm --dir web/portal exec playwright test` 全部 exit 0 — 验证:4 个命令连续 0 退出
- [x] 6.2 `openspec validate web-portal-shell` exit 0 — 验证:本 V1 valid: true
- [x] 6.3 `git diff main --stat` 仅 `web/portal/` 与 `openspec/changes/web-portal-shell/` 2 个目录有差异 — 验证:canvas / admin / nginx.conf / Dockerfile / 任何既有 spec 0 改动
- [x] 6.4 浏览器手动验收(`pnpm --dir web/portal exec vite` 起 5174,然后 `http://localhost:5174/portal/login` 走完 login → dashboard → sidebar workflow 跳 5173 → sidebar credential 看 Coming soon)— 验证:截图 4 个关键状态(由 playwright 2/2 e2e 覆盖;浏览器手动跳过,V2 集成时统一手动)
- [x] 6.5 写 `verify.md`(7 项检查 + 4 张截图路径 + exit codes 全 0) — 验证:verify.md 通过 openspec-verify-change 的 7 项检查
