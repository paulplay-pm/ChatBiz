# ChatBiz Admin Web

ChatBiz 企业 AI Agent 平台的管理控制台前端骨架。**当前 change（`admin-bootstrap`）只建骨架，不含业务逻辑** —— 14 个左侧菜单全部指向 `PlaceholderView`，等后续 change 落地。

## 技术栈

- Vite 5 + React 18 + TypeScript 5（strict + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes`）
- Tailwind CSS 3.4（色板复用 `docs/prototype.html` 的 `ink-*` / `brand-*`）
- React Router 6 + SWR 2
- FontAwesome 6 Solid（`fas fa-*`）
- Vitest 1 + jsdom + @testing-library/react 14（单测）
- Playwright 1.40+ Chromium（E2E）

## 开发命令

```bash
pnpm install            # 装依赖（Node ≥ 20）
pnpm dev                # 启动 Vite dev server → http://localhost:5173
pnpm build              # 生产构建到 dist/
pnpm preview            # 预览生产 build
pnpm typecheck          # tsc --noEmit
pnpm test               # vitest 单测
pnpm test:watch         # vitest watch 模式
pnpm e2e                # playwright E2E
```

首次跑 E2E 前需要装浏览器：
```bash
npx playwright install chromium
```

## 目录结构

```
web/admin/
├── index.html                  # Vite 入口
├── vite.config.ts              # Vite + plugin-react + tsconfig-paths
├── vitest.config.ts            # Vitest + jsdom + @ alias
├── playwright.config.ts        # Playwright + Chromium + webServer 自启 dev
├── tailwind.config.js          # 色板：ink-50~900 + brand-50/500~900
├── postcss.config.js           # tailwindcss + autoprefixer
├── tsconfig.json               # strict + paths @/* → ./src/*
├── tsconfig.node.json          # vite/vitest/playwright config 用
├── src/
│   ├── main.tsx                # React 挂载 + CSS 入口
│   ├── App.tsx                 # RouterProvider 顶层
│   ├── index.css               # @tailwind base/components/utilities
│   ├── vite-env.d.ts           # vite/client 类型声明
│   ├── components/
│   │   ├── AppShell.tsx        # 双栏布局 + header + Outlet
│   │   ├── SideNav.tsx         # 14 menu item + NavLink active 高亮
│   │   └── HealthIndicator.tsx # 健康圆点（绿/黄/红/灰）
│   ├── views/
│   │   └── PlaceholderView.tsx # 14 个路由的占位卡片
│   ├── router/
│   │   └── index.tsx           # createBrowserRouter + 14 路由 + / redirect + 404
│   ├── api/
│   │   └── health.ts           # useHealth() SWR hook → :8004/healthz
│   ├── config/
│   │   └── menuItems.ts        # MENU_ITEMS 单一来源（SideNav + router 共用）
│   └── types/
│       └── index.ts            # HealthStatus / MenuItem 共享类型
├── tests/unit/
│   ├── setup.ts                # 引 @testing-library/jest-dom 匹配器
│   └── AppShell.test.tsx       # 14 menu item smoke 测试
└── e2e/
    └── admin-bootstrap.spec.ts  # /mcp-tools deep-link smoke E2E
```

## 后续 change 怎么 mount 业务视图

1. 在 `src/views/` 新建业务视图组件（例：`McpToolsView.tsx`）。
2. 在 `src/router/index.tsx` 把对应 path 的 element 替换：
   ```tsx
   import { lazy } from "react";
   const McpToolsView = lazy(() =>
     import("@/views/McpToolsView").then((m) => ({ default: m.McpToolsView })),
   );
   // 在 placeholderRoutes 之后 push 一个 override，或者直接改 placeholderRoutes 的生成逻辑
   ```
3. SideNav 不需要改 —— 仍然显示 "MCP 工具"，点击后路由到新视图。
4. 后端联调 client 放 `src/api/<feature>.ts`，参考 `api/health.ts` 写 SWR fetcher。

## 端口

- `5173` Vite dev server（仅 dev）
- `8004` `chatbiz-mcp` 后端（health check 目标，与 CLAUDE.md 端口表对齐）

> **5173 冲突排查**：若启动报 `Port 5173 is already in use`，先看 `docker ps | grep 5173`。
> 若是历史 `chatbiz-web` 容器占用，本 change 决议（design.md D10）是 **不引 admin docker
> 容器**，因此可临时 `docker stop chatbiz-web` 让路；后续 V1.0 由 `admin-deploy` change
> 统一两者端口分配。

后续生产部署由 `admin-deploy` change 负责（nginx + docker-compose）。
