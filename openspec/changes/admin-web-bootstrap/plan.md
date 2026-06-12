# admin-bootstrap Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task.

**Goal:** 在 `web/admin/` 建最小前端骨架（Vite 5 + React 18 + TS strict + Tailwind 3.4 + Router 6 + SWR + 14 menu item + PlaceholderView + 1 vitest + 1 playwright），**不**引业务逻辑，**不**引鉴权，**不**引 docker-compose 容器。完成后 `mcp-server-management-ui` 的 task 7.1-7.8 + 8.1-8.2 解 BLOCKED。

**Architecture:** Vite 5 + React 18 + TypeScript strict + Tailwind 3.4（色板复用 `docs/prototype.html`） + React Router 6（14 路由 + `/` redirect） + SWR（health 探活） + 14 个 menu item SideNav + PlaceholderView（未实现路由的占位）。**不**引业务逻辑，**不**引鉴权。视觉 1:1 复用 prototype.html。

**Tech Stack:**
- Node ≥ 20（engines 锁定）
- pnpm 10.x
- Vite 5 + @vitejs/plugin-react 4
- React 18 + react-dom 18
- TypeScript 5 (strict mode)
- Tailwind CSS 3.4 + postcss + autoprefixer
- React Router 6
- SWR 2
- @fortawesome/fontawesome-free 6
- clsx 2
- Vitest 1 + @testing-library/react 14 + jsdom 24
- @playwright/test 1.40

---

> **OPT — writing-plans skill fallback**：
> 当前 session 的 skills 列表**未**装载 `superpowers:writing-plans`（plugin 缓存里有但未 enable）。按 schema `plan.instruction` 提示手写。
> 模式：节级 micro-step 模板 + 关键 task 完整展开。apply 阶段由 subagent-driven-development 按本 plan 跑——agent 应在每个 task 落地前**自行展开** micro-step，不机械照抄。

---

## Task 1.1 ★: pnpm init + Vite + React TS template

**Files:**
- Create: `web/admin/package.json`
- Create: `web/admin/tsconfig.json`
- Create: `web/admin/tsconfig.node.json`
- Create: `web/admin/vite.config.ts`
- Create: `web/admin/index.html`
- Create: `web/admin/src/main.tsx` (placeholder)
- Create: `web/admin/src/App.tsx` (placeholder)
- Create: `web/admin/.gitignore`

**Step 1**: Bootstrap project
```bash
mkdir -p web/admin
cd web/admin
pnpm init
```

**Step 2**: Install runtime + dev deps (one shot)
```bash
pnpm add react@^18 react-dom@^18 react-router-dom@^6 swr@^2 @fortawesome/fontawesome-free@^6 clsx@^2
pnpm add -D vite@^5 @vitejs/plugin-react@^4 typescript@^5 \
  @types/react @types/react-dom @types/node \
  tailwindcss@^3.4 postcss autoprefixer \
  vitest@^1 @testing-library/react@^14 @testing-library/jest-dom@^6 jsdom@^24 \
  @playwright/test@^1.40 vite-tsconfig-paths@^4
```
Expected: 0 errors, pnpm-lock.yaml generated

**Step 3**: Write `tsconfig.json` (strict + alias)
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "useDefineForClassFields": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src", "tests", "e2e"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

**Step 4**: Write `tsconfig.node.json`
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts", "vitest.config.ts", "playwright.config.ts"]
}
```

**Step 5**: Write `vite.config.ts`
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  server: { port: 5173, strictPort: true },
});
```

**Step 6**: Write `index.html`
```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ChatBiz Admin</title>
  </head>
  <body class="bg-ink-50 text-ink-900 h-screen overflow-hidden">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**Step 7**: Write `src/main.tsx` (placeholder, will replace in task 4.3)
```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

const root = document.getElementById("root");
if (!root) throw new Error("root element not found");
createRoot(root).render(<div>Loading...</div>);
```

**Step 8**: Write `.gitignore`
```
node_modules/
dist/
.vite/
coverage/
test-results/
playwright-report/
*.log
.DS_Store
```

**Step 9**: Verify
```bash
cd web/admin && pnpm tsc --noEmit
```
Expected: exit 0

**Step 10**: Commit
```bash
cd /Users/paulwang/work/ChatBiz
git add web/admin/{package.json,pnpm-lock.yaml,tsconfig.json,tsconfig.node.json,vite.config.ts,index.html,src/main.tsx,.gitignore}
git commit -m "feat(admin): bootstrap Vite 5 + React 18 + TS strict"
```

---

## Task 1.2: package.json engines + type:module
- **Step 1**: Edit `package.json` add `"type": "module"` and `"engines": { "node": ">=20" }`
- **Step 2**: Run `pnpm install` to refresh lockfile
- **Step 3**: Commit

## Task 1.3: Verify tsc --noEmit
- (covered in 1.1 step 9)

---

## Task 2.1: vite.config.ts (done in 1.1 step 5)
## Task 2.2: index.html (done in 1.1 step 6)

---

## Task 3.1 ★: Tailwind init
- **Step 1**: `cd web/admin && pnpm dlx tailwindcss init -p`
- **Step 2**: Verify `tailwind.config.js` + `postcss.config.js` exist
- **Step 3**: Edit `tailwind.config.js`:
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          50: '#f9fafb', 100: '#f3f4f6', 200: '#e5e7eb', 300: '#d1d5db',
          400: '#9ca3af', 500: '#6b7280', 600: '#4b5563', 700: '#374151',
          800: '#1f2937', 900: '#111827',
        },
        brand: {
          500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8',
          800: '#1e40af', 900: '#1e3a8a',
        },
      },
    },
  },
  plugins: [],
};
```
- **Step 4**: Commit

## Task 3.2: src/index.css with Tailwind directives
- **Step 1**: Create `web/admin/src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```
- **Step 2**: Verify `pnpm build` compiles without error
- **Step 3**: Commit

## Task 3.3: import fontawesome CSS in main.tsx
- **Step 1**: Edit `src/main.tsx` add `import "@fortawesome/fontawesome-free/css/all.min.css"; import "./index.css";`
- **Step 2**: Verify `pnpm dev` → browser → `<i class="fas fa-robot">` renders
- **Step 3**: Commit

## Task 3.4: tailwind color verification test
- **Step 1**: In `App.tsx` placeholder, add `<div class="text-ink-900 bg-ink-50 p-4">test</div>`
- **Step 2**: Browser inspect → computed `color: rgb(17, 24, 39)`, `background-color: rgb(249, 250, 251)`
- **Step 3**: Commit (combined with 3.3)

---

## Task 4.1 ★: SideNav.tsx
**Files:** Create `web/admin/src/components/SideNav.tsx`

**Step 1**: Write component
```tsx
import { NavLink } from "react-router-dom";
import clsx from "clsx";

const MENU_ITEMS: ReadonlyArray<{
  name: string; href: string; icon: string; changeName: string;
}> = [
  { name: "工作流", href: "/workflow", icon: "fa-th-large", changeName: "workflow-engine" },
  { name: "Agent", href: "/agent", icon: "fa-robot", changeName: "agent-runtime" },
  { name: "知识库", href: "/knowledge", icon: "fa-book", changeName: "knowledge-base" },
  { name: "模板广场", href: "/templates", icon: "fa-clone", changeName: "template-marketplace" },
  { name: "团队共享", href: "/team", icon: "fa-users", changeName: "team-sharing" },
  { name: "插件市场", href: "/plugins", icon: "fa-puzzle-piece", changeName: "plugin-marketplace" },
  { name: "模型管理", href: "/models", icon: "fa-microchip", changeName: "model-management" },
  { name: "通道管理", href: "/channels", icon: "fa-route", changeName: "channel-management" },
  { name: "凭证管理", href: "/credentials", icon: "fa-key", changeName: "credential" },
  { name: "技能管理", href: "/skills", icon: "fa-magic", changeName: "skill-management" },
  { name: "MCP 工具", href: "/mcp-tools", icon: "fa-plug", changeName: "mcp-server-management-ui" },
  { name: "中间件链", href: "/middleware", icon: "fa-link", changeName: "middleware-chain" },
  { name: "监控", href: "/monitoring", icon: "fa-chart-line", changeName: "monitoring" },
  { name: "日志", href: "/logs", icon: "fa-file-alt", changeName: "log-query" },
] as const;

export function SideNav(): JSX.Element {
  return (
    <nav aria-label="主导航" className="w-64 bg-white border-r border-ink-200 flex flex-col h-full">
      <div className="px-4 py-4 border-b border-ink-200 flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center">
          <i className="fas fa-robot text-white text-sm" aria-hidden="true" />
        </div>
        <span className="font-semibold text-sm text-ink-800">ChatBiz Admin</span>
      </div>
      <div className="px-4 py-2 text-[11px] font-semibold text-ink-400 uppercase tracking-wider">工作区</div>
      <ul className="flex-1 overflow-y-auto px-2 space-y-0.5">
        {MENU_ITEMS.map((item) => (
          <li key={item.href}>
            <NavLink
              to={item.href}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2 px-3 h-9 rounded-lg text-sm transition-colors",
                  isActive
                    ? "bg-brand-50 text-brand-600 font-medium"
                    : "text-ink-700 hover:bg-ink-100"
                )
              }
            >
              <i className={`fas ${item.icon} w-4 text-center`} aria-hidden="true" />
              <span>{item.name}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
```

**Step 2**: Verify `pnpm dev` → 14 menu items visible
**Step 3**: Commit

## Task 4.2 ★: AppShell.tsx
**Files:** Create `web/admin/src/components/AppShell.tsx`

**Step 1**: Write component
```tsx
import { Outlet } from "react-router-dom";
import { SideNav } from "./SideNav";
import { HealthIndicator } from "./HealthIndicator";

export function AppShell(): JSX.Element {
  return (
    <div className="flex h-screen">
      <SideNav />
      <main className="flex-1 flex flex-col h-full">
        <header className="h-14 bg-white border-b border-ink-200 flex items-center px-5 gap-4">
          <h1 className="font-semibold text-sm text-ink-800">ChatBiz Admin</h1>
          <div className="ml-auto flex items-center gap-3">
            <HealthIndicator />
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white text-sm font-bold">
              张
            </div>
          </div>
        </header>
        <div className="flex-1 p-6 overflow-y-auto bg-ink-50">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
```

**Step 2**: Commit (combined with 4.3 once HealthIndicator exists)

## Task 4.3 ★: HealthIndicator.tsx + main.tsx wiring
**Files:** Create `web/admin/src/components/HealthIndicator.tsx`, modify `src/main.tsx` + `src/App.tsx`

**Step 1**: Create `health.ts` (task 6.2)

**Step 2**: Create `HealthIndicator.tsx`
```tsx
import { useHealth } from "@/api/health";

export function HealthIndicator(): JSX.Element {
  const { data } = useHealth();
  const status = data?.status ?? "unknown";
  const color = {
    healthy: "bg-green-500",
    degraded: "bg-yellow-500",
    down: "bg-red-500",
    unknown: "bg-ink-400",
  }[status];
  return (
    <div className="flex items-center gap-2 text-xs text-ink-500" aria-label={`服务健康：${status}`}>
      <span className={`w-2 h-2 rounded-full ${color}`} aria-hidden="true" />
      <span>{status}</span>
    </div>
  );
}
```

**Step 3**: Update `src/App.tsx`
```tsx
import { RouterProvider } from "react-router-dom";
import { router } from "./router";

export default function App(): JSX.Element {
  return <RouterProvider router={router} />;
}
```

**Step 4**: Update `src/main.tsx`
```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fortawesome/fontawesome-free/css/all.min.css";
import "./index.css";
import App from "./App";

const root = document.getElementById("root");
if (!root) throw new Error("root element not found");
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

**Step 5**: Verify `pnpm dev` → browser shows AppShell + 14 menu + HealthIndicator
**Step 6**: Commit

---

## Task 5.1: react-router-dom install (done in 1.1 step 2)

## Task 5.2 ★: PlaceholderView.tsx
**Files:** Create `web/admin/src/views/PlaceholderView.tsx`

**Step 1**: Write component
```tsx
interface PlaceholderViewProps {
  menuItemName: string;
  changeName: string;
}

export function PlaceholderView({ menuItemName, changeName }: PlaceholderViewProps): JSX.Element {
  return (
    <div className="max-w-md mx-auto mt-24 bg-white rounded-xl border border-dashed border-ink-300 p-12 text-center">
      <i className="fas fa-plus text-2xl text-ink-400 mb-4 block" aria-hidden="true" />
      <h2 className="text-xl font-semibold text-ink-800 mb-2">🚧 {menuItemName} 即将推出</h2>
      <p className="text-sm text-ink-500">由后续 change {changeName} 落地</p>
    </div>
  );
}
```

**Step 2**: Commit

## Task 5.3 ★: router/index.tsx
**Files:** Create `web/admin/src/router/index.tsx`

**Step 1**: Write router
```tsx
import { lazy } from "react";
import { createBrowserRouter, Navigate, type RouteObject } from "react-router-dom";
import { AppShell } from "@/components/AppShell";

const PlaceholderView = lazy(() =>
  import("@/views/PlaceholderView").then((m) => ({ default: m.PlaceholderView })),
);

const ROUTES_WITH_META: ReadonlyArray<{ path: string; menuItemName: string; changeName: string }> = [
  { path: "/workflow", menuItemName: "工作流", changeName: "workflow-engine" },
  { path: "/agent", menuItemName: "Agent", changeName: "agent-runtime" },
  { path: "/knowledge", menuItemName: "知识库", changeName: "knowledge-base" },
  { path: "/templates", menuItemName: "模板广场", changeName: "template-marketplace" },
  { path: "/team", menuItemName: "团队共享", changeName: "team-sharing" },
  { path: "/plugins", menuItemName: "插件市场", changeName: "plugin-marketplace" },
  { path: "/models", menuItemName: "模型管理", changeName: "model-management" },
  { path: "/channels", menuItemName: "通道管理", changeName: "channel-management" },
  { path: "/credentials", menuItemName: "凭证管理", changeName: "credential" },
  { path: "/skills", menuItemName: "技能管理", changeName: "skill-management" },
  { path: "/mcp-tools", menuItemName: "MCP 工具", changeName: "mcp-server-management-ui" },
  { path: "/middleware", menuItemName: "中间件链", changeName: "middleware-chain" },
  { path: "/monitoring", menuItemName: "监控", changeName: "monitoring" },
  { path: "/logs", menuItemName: "日志", changeName: "log-query" },
];

const childRoutes: RouteObject[] = ROUTES_WITH_META.map(({ path, menuItemName, changeName }) => ({
  path,
  element: (
    <PlaceholderView menuItemName={menuItemName} changeName={changeName} />
  ),
}));

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/workflow" replace /> },
      ...childRoutes,
    ],
  },
];

export const router = createBrowserRouter(routes);
```

**Step 2**: Verify `pnpm dev` → browser → deep link `/mcp-tools` shows PlaceholderView + SideNav 激活
**Step 3**: Commit

---

## Task 6.1: swr install (done in 1.1 step 2)
## Task 6.2 ★: api/health.ts
**Files:** Create `web/admin/src/api/health.ts`

**Step 1**: Write
```ts
import useSWR from "swr";
import type { HealthStatus } from "@/types";

interface HealthResponse { status: HealthStatus }

async function fetcher(url: string): Promise<HealthResponse> {
  try {
    const res = await fetch(url);
    if (!res.ok) return { status: "down" };
    return await res.json();
  } catch {
    return { status: "down" };
  }
}

export function useHealth(baseUrl: string = "http://localhost:8004"): { data?: HealthResponse } {
  const { data } = useSWR<HealthResponse>(
    `${baseUrl}/healthz`,
    fetcher,
    { refreshInterval: 5000, revalidateOnFocus: false },
  );
  return { data };
}
```

**Step 2**: Verify `pnpm dev` → browser console sees fetch attempts every 5s
**Step 3**: Commit

## Task 6.3: HealthIndicator (done in 4.3 step 2)

---

## Task 7.1 ★: types/index.ts
**Files:** Create `web/admin/src/types/index.ts`

**Step 1**: Write
```ts
export type HealthStatus = "healthy" | "degraded" | "down" | "unknown";

export interface MenuItem {
  readonly name: string;
  readonly href: string;
  readonly icon: string;
  readonly changeName: string;
}
```

**Step 2**: Verify `pnpm tsc --noEmit` 0 errors
**Step 3**: Commit

## Task 7.2: .gitignore (done in 1.1 step 8)
## Task 7.3 ★: README.md
**Files:** Create `web/admin/README.md`

**Step 1**: Write README
```markdown
# ChatBiz Admin Web

## 开发
- `pnpm install` 安装依赖
- `pnpm dev` 启动 Vite dev server on http://localhost:5173
- `pnpm build` 生产构建到 `dist/`
- `pnpm test` 跑 vitest
- `pnpm e2e` 跑 Playwright

## 目录
- `src/components/` 复用组件 (SideNav, AppShell, HealthIndicator)
- `src/views/` 视图 (PlaceholderView + 后续业务视图)
- `src/router/` 路由配置
- `src/api/` 后端联调 client
- `src/types/` 共用 TypeScript 类型
- `tests/unit/` vitest 单测
- `e2e/` Playwright E2E

## 后续 change 怎么 mount
- 在 `src/router/index.tsx` import 你的视图
- 把路由 push 到 `childRoutes` 数组（替换对应 path 的 PlaceholderView）
- 在 `src/api/` 加你的后端 client
```

**Step 2**: Commit

---

## Task 8.1: vitest deps (done in 1.1 step 2)
## Task 8.2 ★: vitest.config.ts
**Files:** Create `web/admin/vitest.config.ts`

**Step 1**: Write
```ts
import { defineConfig } from "vitest/config";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [tsconfigPaths()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/unit/setup.ts"],
    coverage: { provider: "v8", reporter: ["text", "html"], thresholds: { lines: 80, functions: 80, branches: 70, statements: 80 } },
  },
});
```

**Step 2**: Commit

## Task 8.3 ★: tests/unit/setup.ts
**Files:** Create `web/admin/tests/unit/setup.ts`

**Step 1**: Write
```ts
import "@testing-library/jest-dom";
```

**Step 2**: Commit

## Task 8.4 ★: tests/unit/AppShell.test.tsx
**Files:** Create `web/admin/tests/unit/AppShell.test.tsx`

**Step 1**: Write
```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppShell } from "@/components/AppShell";

const EXPECTED_HREFS = [
  "/workflow", "/agent", "/knowledge", "/templates", "/team",
  "/plugins", "/models", "/channels", "/credentials", "/skills",
  "/mcp-tools", "/middleware", "/monitoring", "/logs",
];

describe("AppShell", () => {
  it("renders 14 menu items", () => {
    render(
      <MemoryRouter>
        <AppShell />
      </MemoryRouter>,
    );
    for (const href of EXPECTED_HREFS) {
      expect(screen.getByRole("link", { name: new RegExp(href.slice(1)) })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("link")).toHaveLength(EXPECTED_HREFS.length);
  });
});
```

**Step 2**: Verify `pnpm test` 1/1 pass
**Step 3**: Commit

## Task 8.5: @playwright/test install (done in 1.1 step 2)

## Task 8.6 ★: playwright.config.ts
**Files:** Create `web/admin/playwright.config.ts`

**Step 1**: Write
```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "pnpm dev",
    port: 5173,
    reuseExistingServer: !process.env["CI"],
    timeout: 30_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
```

**Step 2**: Commit

## Task 8.7 ★: e2e/admin-bootstrap.spec.ts
**Files:** Create `web/admin/e2e/admin-bootstrap.spec.ts`

**Step 1**: Write
```ts
import { test, expect } from "@playwright/test";

test("Open /mcp-tools and verify SideNav + Placeholder", async ({ page }) => {
  await page.goto("/mcp-tools");
  await expect(page).toHaveURL(/\/mcp-tools$/);
  await expect(page.getByRole("navigation", { name: "主导航" })).toBeVisible();
  await expect(page.getByRole("link", { name: "MCP 工具" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText(/即将推出/)).toBeVisible();
});
```

**Step 2**: Run `npx playwright install chromium`
**Step 3**: Verify `pnpm e2e` 1/1 pass
**Step 4**: Commit

---

## Task 9.1: full verify
- **Step 1**: `cd web/admin && pnpm tsc --noEmit` → exit 0
- **Step 2**: `pnpm build` → exit 0
- **Step 3**: `pnpm test` → 1/1
- **Step 4**: `pnpm e2e` → 1/1
- **Step 5**: All four exit 0

## Task 9.2: repo-root .gitignore
- **Step 1**: Edit `/Users/paulwang/work/ChatBiz/.gitignore` add `web/admin/{node_modules,dist,.vite,coverage,test-results,playwright-report}/`
- **Step 2**: Verify `git status` doesn't list those
- **Step 3**: Commit

## Task 9.3-9.5: post-apply (retrospective + validate)
- Will be filled in apply phase after commit

---

## 配对验证总结

| 编码 | 配对验证 |
|---|---|
| 1.1-1.3 | 1.1 step 9 tsc --noEmit |
| 2.1-2.2 | 2.2 step 9 manual browser |
| 3.1-3.4 | 3.2 pnpm build, 3.3 browser |
| 4.1-4.3 | 4.3 step 5 browser |
| 5.1-5.3 | 5.3 step 2 browser deep link |
| 6.1-6.3 | 6.2 step 2 console fetch |
| 7.1-7.3 | 7.1 tsc, 7.3 manual read |
| 8.1-8.8 | 8.4 vitest 1/1, 8.7 playwright 1/1 |
| 9.1-9.5 | 9.1 all 4 commands exit 0 |

---

## Critical Path 覆盖

**本 change 不**直接覆盖 eng-review Test #2 4 critical path 任何一个（纯前端骨架）——但**提供测试框架**让后续 change 覆盖：

| Critical Path | 后续 change 覆盖 |
|---|---|
| ① paul 财务月报 | workflow-engine |
| ② 网关 PII | gateway-egress-enforcement-p0 |
| ③ 人工审批续接 | workflow-engine |
| ④ 插件加载降级 | mcp-server-management-ui task 9.2 |

**提供**：
- Vitest 1.0 + jsdom 单测框架
- Playwright 1.40 + Chromium E2E 框架
- TypeScript strict 编译检查

---

## 估算时间（per tasks.md）

~9h（含 pnpm install 时间 + Playwright 浏览器下载 + E2E 调试）
