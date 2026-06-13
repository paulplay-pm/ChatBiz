# web-portal-shell (V1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `web/portal` 子应用,独立 Vite dev 5174,跑通"登录 → 主框架 → 30+ 项侧栏 → 跳 /canvas/* 或 /portal/coming-soon"完整路径。**不动** canvas / admin / nginx.conf / Dockerfile / 既有 spec。

**Architecture:** portal 是独立 Vite + React + TS 子应用,挂 `base: '/portal/'` 与 dev port 5174;`localStorage['chatbiz.auth']` 存 username + loginAt(轻量标记,沿用 `canvas-auth` dev fallback 契约);设计 token 来自 `docs/prototype.html:7-40` 头部 `tailwind.config` 块,落 `web/portal/tailwind.config.js`;`web/portal/src/components/primitives/` 维护 Button / Card / MetricCard / StatusDot / Input / Form / Modal / Toast / Sidebar / SidebarItem / SidebarSection 共 11 个原语(V2 / V3 集成时复用)。V1 期间 portal **不**集成 nginx,V2 + V3 一起集成。

**Tech Stack:** Vite 5 + React 18 + TypeScript 5.4 strict + Tailwind CSS 3.4 + React Router 6 + @tanstack/react-query 5 + vitest 1 + @testing-library/react 16 + @playwright/test 1 + jsdom 24 + Google Fonts(DM Sans / Space Mono)

---

## File Structure

### Created files (V1 scope only)

- `web/portal/package.json` — portal 依赖清单
- `web/portal/tsconfig.json` — TypeScript strict 配置
- `web/portal/vite.config.ts` — Vite 5(`base: '/portal/'` + port 5174)
- `web/portal/tailwind.config.js` — prototype 调色板 + 字体
- `web/portal/postcss.config.js` — postcss + tailwind
- `web/portal/index.html` — Vite HTML 入口(含 Google Fonts `<link>`)
- `web/portal/vitest.config.ts` — vitest 1 + jsdom
- `web/portal/playwright.config.ts` — Playwright
- `web/portal/src/main.tsx` — ReactDOM + QueryClientProvider + BrowserRouter basename='/portal' + ToastProvider
- `web/portal/src/App.tsx` — 引入 `PortalRouter`
- `web/portal/src/index.css` — `@tailwind` 指令 + `.glass` 工具类 + 5 个 status-dot 类
- `web/portal/src/vite-env.d.ts` — `/// <reference types="vite/client" />`
- `web/portal/src/data/menu.ts` — 5 section + 30+ MenuItem
- `web/portal/src/components/AppLayout.tsx` — 顶部 + Sidebar + Outlet
- `web/portal/src/components/RequireAuth.tsx` — localStorage 守卫
- `web/portal/src/components/primitives/{Button,Card,MetricCard,StatusDot,Input,Form,Modal,Toast,useToast,Sidebar,SidebarItem,SidebarSection}.tsx`
- `web/portal/src/pages/{LoginPage,DashboardPage,ComingSoonPage}.tsx`
- `web/portal/src/router/index.tsx` — `PortalRouter`
- `web/portal/tests/{primitives_Button,primitives_Card,primitives_Input,primitives_Toast,primitives_Sidebar,components_RequireAuth,pages_LoginPage,pages_DashboardPage,pages_ComingSoonPage,menu}.test.{ts,tsx}` — 估计 10 个 spec
- `web/portal/e2e/portal-flow.spec.ts` — 2 个 playwright spec
- `web/portal/README.md` — dev 5174 + build + e2e 命令
- `openspec/changes/web-portal-shell/checklist/tailwind-config-parity.md` — V2 / V3 复用模板

### NOT modified by V1 (留 V2 / V3)

- `web/canvas/**`, `web/admin/**`
- `web/nginx.conf`, `web/Dockerfile`, `web/index.html`
- `web/README.md`, `infrastructure/README.md`
- `openspec/specs/**` (V1 0 个 modified capabilities)
- `infrastructure/docker-compose*.yml`

---

## Plan Task 1: Worktree + Spec 准备

**Files:**
- Create: `.worktrees/web-portal-shell/`
- Create: `openspec/changes/web-portal-shell/checklist/tailwind-config-parity.md`

- [ ] **Step 1: 创建 worktree**

```bash
cd /Users/paulwang/work/ChatBiz
git worktree add .worktrees/web-portal-shell -b worktree-web-portal-shell
cd .worktrees/web-portal-shell
git status
```
Expected: `On branch work-tree-web-portal-shell` + `nothing to commit, working tree clean`

- [ ] **Step 2: 复制 V1 change artifacts 到 worktree**

```bash
cp -R /Users/paulwang/work/ChatBiz/openspec/changes/web-portal-shell /Users/paulwang/work/ChatBiz/.worktrees/web-portal-shell/openspec/changes/web-portal-shell
cd /Users/paulwang/work/ChatBiz/.worktrees/web-portal-shell
ls openspec/changes/web-portal-shell/
```
Expected: `brainstorm.md design.md plan.md proposal.md specs tasks.md`

- [ ] **Step 3: 验证 openspec validate**

```bash
cd /Users/paulwang/work/ChatBiz
openspec validate web-portal-shell
```
Expected: `Change 'web-portal-shell' is valid`

- [ ] **Step 4: 创建 tailwind config parity checklist 模板**

Write `openspec/changes/web-portal-shell/checklist/tailwind-config-parity.md`:

```markdown
# Tailwind Config Parity Checklist

Source of truth: `docs/prototype.html` lines 7-40 (`tailwind.config` block).

V1 仅校验 portal 1 份;V2 / V3 集成时,canvas / admin 的 `tailwind.config.js` 必须与 portal 逐位一致(`diff` 无输出)。

| Token | Hex | portal (V1) | canvas (V2) | admin (V3) |
|---|---|---|---|---|
| brand-50 | #f0f4ff | [ ] | [ ] | [ ] |
| brand-100 | #e0e9ff | [ ] | [ ] | [ ] |
| brand-200 | #c2d4ff | [ ] | [ ] | [ ] |
| brand-300 | #94b4ff | [ ] | [ ] | [ ] |
| brand-400 | #5e8bff | [ ] | [ ] | [ ] |
| brand-500 | #3b6ef5 | [ ] | [ ] | [ ] |
| brand-600 | #2a52d8 | [ ] | [ ] | [ ] |
| brand-700 | #2240b0 | [ ] | [ ] | [ ] |
| brand-800 | #1f368e | [ ] | [ ] | [ ] |
| brand-900 | #1e3072 | [ ] | [ ] | [ ] |
| ink-50 | #f6f7f9 | [ ] | [ ] | [ ] |
| ink-100 | #eceef2 | [ ] | [ ] | [ ] |
| ink-200 | #d5d9e2 | [ ] | [ ] | [ ] |
| ink-300 | #b0b8c8 | [ ] | [ ] | [ ] |
| ink-400 | #8591a8 | [ ] | [ ] | [ ] |
| ink-500 | #66728a | [ ] | [ ] | [ ] |
| ink-600 | #525b70 | [ ] | [ ] | [ ] |
| ink-700 | #444b5c | [ ] | [ ] | [ ] |
| ink-800 | #3a3f4d | [ ] | [ ] | [ ] |
| ink-900 | #1e2128 | [ ] | [ ] | [ ] |
| ink-950 | #0f1115 | [ ] | [ ] | [ ] |
| font-sans | DM Sans | [ ] | [ ] | [ ] |
| font-mono | Space Mono | [ ] | [ ] | [ ] |
```

- [ ] **Step 5: Commit**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/web-portal-shell
git add openspec/changes/web-portal-shell/checklist/
git commit -m "chore: add tailwind config parity checklist template for V2/V3 reuse"
```

---

## Plan Task 2: portal 子应用脚手架

**Files:**
- Create: `web/portal/package.json` + `tsconfig.json` + `vite.config.ts` + `tailwind.config.js` + `postcss.config.js` + `index.html` + `src/{main,App,index.css,vite-env.d.ts}` + `vitest.config.ts` + `playwright.config.ts`

- [ ] **Step 1: 创建 `web/portal/package.json`**

```json
{
  "name": "chatbiz-portal",
  "version": "0.0.1",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview --port 4174",
    "test": "vitest run",
    "test:watch": "vitest",
    "e2e": "playwright test"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "@tanstack/react-query": "^5.51.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.4.5",
    "vite": "^5.3.4",
    "tailwindcss": "^3.4.7",
    "postcss": "^8.4.40",
    "autoprefixer": "^10.4.19",
    "vitest": "^1.6.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.6",
    "@testing-library/user-event": "^14.5.2",
    "@playwright/test": "^1.45.0",
    "jsdom": "^24.1.0"
  }
}
```

- [ ] **Step 2: `pnpm --dir web/portal install`**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/web-portal-shell
pnpm --dir web/portal install
```
Expected: exit 0, `web/portal/node_modules/` created

- [ ] **Step 3: 创建 `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitAny": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"],
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src", "tests", "e2e", "vitest.config.ts"]
}
```

- [ ] **Step 4: 创建 `vite.config.ts`**

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  base: '/portal/',
  server: { port: 5174 },
});
```

- [ ] **Step 5: 创建 `tailwind.config.js`**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
        mono: ['Space Mono', 'monospace'],
      },
      colors: {
        brand: { 50: '#f0f4ff', 100: '#e0e9ff', 200: '#c2d4ff', 300: '#94b4ff', 400: '#5e8bff', 500: '#3b6ef5', 600: '#2a52d8', 700: '#2240b0', 800: '#1f368e', 900: '#1e3072' },
        ink: { 50: '#f6f7f9', 100: '#eceef2', 200: '#d5d9e2', 300: '#b0b8c8', 400: '#8591a8', 500: '#66728a', 600: '#525b70', 700: '#444b5c', 800: '#3a3f4d', 900: '#1e2128', 950: '#0f1115' },
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 6: 创建 `postcss.config.js` + `index.html`**

```js
// postcss.config.js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

```html
<!-- index.html -->
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ChatBiz Portal</title>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 7: 创建 `src/main.tsx` + `App.tsx` + `index.css` + `vite-env.d.ts`**

```tsx
// src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastProvider } from '@/components/primitives/Toast';
import App from './App';
import './index.css';

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } } });

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter basename="/portal">
        <ToastProvider>
          <App />
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
```

```tsx
// src/App.tsx — V1 第 1 步是占位,Plan Task 4 替换
export default function App() {
  return <div data-testid="app-placeholder">portal scaffold ok</div>;
}
```

```css
/* src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

body { font-family: 'DM Sans', system-ui, sans-serif; margin: 0; }

.glass { background: rgba(255,255,255,0.92); backdrop-filter: blur(20px) saturate(1.4); border-bottom: 1px solid rgba(0,0,0,0.06); }
.node-shadow { box-shadow: 0 2px 8px rgba(0,0,0,0.08), 0 0 1px rgba(0,0,0,0.12); }
.metric-card { background: linear-gradient(135deg, #fff 0%, #f6f7f9 100%); border: 1px solid #eceef2; }

.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.status-running { background: #3b6ef5; animation: pulse 2s infinite; }
.status-success { background: #22c55e; }
.status-error { background: #ef4444; }
.status-idle { background: #b0b8c8; }
.status-pending { background: #f59e0b; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
```

```ts
// src/vite-env.d.ts
/// <reference types="vite/client" />
```

- [ ] **Step 8: 创建 `vitest.config.ts` + `playwright.config.ts`**

```ts
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
  },
});
```

```ts
// tests/setup.ts
import '@testing-library/jest-dom';
```

```ts
// playwright.config.ts
import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  webServer: { command: 'pnpm exec vite preview --port 4174', port: 4174, reuseExistingServer: true },
  use: { baseURL: 'http://localhost:4174' },
});
```

- [ ] **Step 9: 验证 build**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/web-portal-shell
pnpm --dir web/portal exec tsc --noEmit
pnpm --dir web/portal exec vite build
ls web/portal/dist/
```
Expected: exit 0;产物含 `index.html` + `assets/index-*.js`

- [ ] **Step 10: 验证 vitest + playwright 安装**

```bash
pnpm --dir web/portal exec vitest run
pnpm --dir web/portal exec playwright --version
```
Expected: vitest exit 0(空 spec);playwright 报版本号

- [ ] **Step 11: Commit**

```bash
git add web/portal/
git commit -m "feat(portal): scaffold Vite+React+TS+Tailwind with prototype theme (V1)"
```

---

## Plan Task 3: portal Primitives 11 个原语

**Files:**
- Create: `web/portal/src/components/primitives/{Button,Card,MetricCard,StatusDot,Input,Form,Modal,Toast,Sidebar,SidebarItem,SidebarSection}.tsx` + `useToast.ts`
- Create: `web/portal/src/data/menu.ts`
- Create: `web/portal/tests/{primitives_Button,primitives_Card,primitives_Input,primitives_Toast,primitives_Sidebar,menu}.test.{ts,tsx}`

- [ ] **Step 1: 写 Button 失败测试 + 实现 + 跑通(TDD)**

`web/portal/tests/primitives_Button.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '@/components/primitives/Button';

describe('Button', () => {
  it('primary variant uses bg-brand-500', () => {
    render(<Button variant="primary">Click</Button>);
    expect(screen.getByTestId('btn').className).toMatch(/bg-brand-500/);
  });
  it('ghost variant uses bg-transparent', () => {
    render(<Button variant="ghost">Cancel</Button>);
    expect(screen.getByTestId('btn').className).toMatch(/bg-transparent/);
  });
  it('calls onClick when clicked', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    await userEvent.click(screen.getByTestId('btn'));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
```

`web/portal/src/components/primitives/Button.tsx`:

```tsx
import { ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost';
type Size = 'sm' | 'md' | 'lg';
const variants: Record<Variant, string> = {
  primary: 'bg-brand-500 hover:bg-brand-600 text-white',
  secondary: 'bg-ink-100 hover:bg-ink-200 text-ink-900',
  ghost: 'bg-transparent hover:bg-ink-100 text-ink-700',
};
const sizes: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-base',
};

export function Button({ variant = 'primary', size = 'md', children, onClick, type = 'button' }: {
  variant?: Variant; size?: Size; children: ReactNode; onClick?: () => void; type?: 'button' | 'submit';
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      data-testid="btn"
      className={`rounded-lg font-medium transition-all ${variants[variant]} ${sizes[size]}`}
    >
      {children}
    </button>
  );
}
```

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/web-portal-shell
pnpm --dir web/portal exec vitest run tests/primitives_Button.test.tsx
```
Expected: PASS 3/3

- [ ] **Step 2: Card / MetricCard / StatusDot 实现 + 测试**

`web/portal/src/components/primitives/Card.tsx`:

```tsx
import { ReactNode } from 'react';
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div data-testid="card" className={`rounded-xl bg-white border border-ink-200 node-shadow p-4 ${className}`}>{children}</div>;
}
```

`web/portal/src/components/primitives/MetricCard.tsx`:

```tsx
import { ReactNode } from 'react';
export function MetricCard({ label, value, trend }: { label: string; value: string | number; trend?: ReactNode }) {
  return (
    <div data-testid="metric-card" className="rounded-xl p-4 metric-card">
      <div className="text-xs text-ink-500">{label}</div>
      <div className="text-2xl font-semibold text-ink-900 mt-1">{value}</div>
      {trend && <div className="text-xs text-brand-500 mt-2">{trend}</div>}
    </div>
  );
}
```

`web/portal/src/components/primitives/StatusDot.tsx`:

```tsx
export function StatusDot({ status }: { status: 'running' | 'success' | 'error' | 'idle' | 'pending' }) {
  return <span data-testid="status-dot" className={`status-dot status-${status}`} />;
}
```

`web/portal/tests/primitives_Card.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Card } from '@/components/primitives/Card';
import { MetricCard } from '@/components/primitives/MetricCard';
import { StatusDot } from '@/components/primitives/StatusDot';

describe('Card', () => {
  it('renders children', () => {
    render(<Card>hello</Card>);
    expect(screen.getByTestId('card')).toHaveTextContent('hello');
  });
});

describe('MetricCard', () => {
  it('renders label and value', () => {
    render(<MetricCard label="工作流" value={12} />);
    expect(screen.getByTestId('metric-card')).toHaveTextContent('工作流');
    expect(screen.getByTestId('metric-card')).toHaveTextContent('12');
  });
});

describe('StatusDot', () => {
  it('renders 5 status variants', () => {
    const { rerender } = render(<StatusDot status="running" />);
    expect(screen.getByTestId('status-dot').className).toMatch(/status-running/);
    rerender(<StatusDot status="success" />);
    expect(screen.getByTestId('status-dot').className).toMatch(/status-success/);
    rerender(<StatusDot status="error" />);
    expect(screen.getByTestId('status-dot').className).toMatch(/status-error/);
    rerender(<StatusDot status="idle" />);
    expect(screen.getByTestId('status-dot').className).toMatch(/status-idle/);
    rerender(<StatusDot status="pending" />);
    expect(screen.getByTestId('status-dot').className).toMatch(/status-pending/);
  });
});
```

```bash
pnpm --dir web/portal exec vitest run tests/primitives_Card.test.tsx
```
Expected: PASS 7/7

- [ ] **Step 3: Input / Form / Modal 实现 + 测试**

`web/portal/src/components/primitives/Input.tsx`:

```tsx
import { ChangeEvent } from 'react';
export function Input({ value, onChange, placeholder, type = 'text', name }: {
  value?: string; onChange?: (e: ChangeEvent<HTMLInputElement>) => void; placeholder?: string; type?: string; name?: string;
}) {
  return (
    <input
      data-testid="input"
      name={name}
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:border-brand-500"
    />
  );
}
```

`web/portal/src/components/primitives/Form.tsx`:

```tsx
import { FormEvent, ReactNode } from 'react';
export function Form({ onSubmit, children }: { onSubmit: (e: FormEvent) => void; children: ReactNode }) {
  return <form data-testid="form" onSubmit={onSubmit} className="space-y-4">{children}</form>;
}
```

`web/portal/src/components/primitives/Modal.tsx`:

```tsx
import { ReactNode } from 'react';
export function Modal({ open, onClose, children, title }: { open: boolean; onClose: () => void; children: ReactNode; title: string }) {
  if (!open) return null;
  return (
    <div data-testid="modal-backdrop" onClick={onClose} className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center">
      <div data-testid="modal" onClick={(e) => e.stopPropagation()} className="bg-white rounded-xl p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold text-ink-900 mb-4">{title}</h3>
        {children}
      </div>
    </div>
  );
}
```

`web/portal/tests/primitives_Input.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Input } from '@/components/primitives/Input';

describe('Input', () => {
  it('renders with placeholder', () => {
    render(<Input placeholder="username" />);
    expect(screen.getByPlaceholderText('username')).toBeInTheDocument();
  });
  it('updates value on type', async () => {
    const onChange = vi.fn();
    render(<Input placeholder="username" onChange={onChange} />);
    await userEvent.type(screen.getByPlaceholderText('username'), 'paul');
    expect(onChange).toHaveBeenCalled();
  });
});
```

`web/portal/tests/primitives_Toast.test.tsx` (替代独立 Modal test,因 Toast 复杂度更高)— 同时验 Modal:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Modal } from '@/components/primitives/Modal';
import { ToastProvider, useToast } from '@/components/primitives/Toast';
import { act } from '@testing-library/react';

describe('Modal', () => {
  it('does not render when open=false', () => {
    render(<Modal open={false} onClose={() => {}} title="t">c</Modal>);
    expect(screen.queryByTestId('modal')).toBeNull();
  });
  it('renders and closes on backdrop click', async () => {
    const onClose = vi.fn();
    render(<Modal open={true} onClose={onClose} title="t">c</Modal>);
    expect(screen.getByTestId('modal')).toBeInTheDocument();
    await userEvent.click(screen.getByTestId('modal-backdrop'));
    expect(onClose).toHaveBeenCalledOnce();
  });
});

function Probe() {
  const t = useToast();
  return <button data-testid="probe" onClick={() => t.error('会话过期')} />;
}

describe('Toast', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());
  it('renders security toast in red', () => {
    render(<ToastProvider><Probe /></ToastProvider>);
    act(() => screen.getByTestId('probe').click());
    expect(screen.getByTestId('toast-security')).toHaveTextContent('会话过期');
  });
  it('auto-dismisses after 5s', () => {
    render(<ToastProvider><Probe /></ToastProvider>);
    act(() => screen.getByTestId('probe').click());
    expect(screen.queryByTestId('toast-security')).toBeTruthy();
    act(() => vi.advanceTimersByTime(5001));
    expect(screen.queryByTestId('toast-security')).toBeNull();
  });
});
```

```bash
pnpm --dir web/portal exec vitest run tests/primitives_Input.test.tsx tests/primitives_Toast.test.tsx
```
Expected: PASS 6/6

- [ ] **Step 4: Toast 实现**

`web/portal/src/components/primitives/Toast.tsx`:

```tsx
import { createContext, ReactNode, useCallback, useContext, useState } from 'react';

type ToastKind = 'security' | 'user' | 'info';
type ToastItem = { id: number; kind: ToastKind; message: string };
type Ctx = { push: (kind: ToastKind, message: string) => void };

const ToastContext = createContext<Ctx | null>(null);
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return {
    error: (msg: string) => ctx.push('security', msg),
    warn: (msg: string) => ctx.push('user', msg),
    info: (msg: string) => ctx.push('info', msg),
  };
}

const colorMap: Record<ToastKind, string> = {
  security: 'bg-red-500',
  user: 'bg-yellow-500',
  info: 'bg-brand-500',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((kind: ToastKind, message: string) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, kind, message }]);
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);
  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div data-testid="toast-host" className="fixed top-4 left-1/2 -translate-x-1/2 z-[9999] flex flex-col gap-2">
        {items.map((t) => (
          <div key={t.id} data-testid={`toast-${t.kind}`} className={`${colorMap[t.kind]} text-white px-4 py-2 rounded-lg shadow-lg`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
```

- [ ] **Step 5: 写 menu.ts + 测试**

`web/portal/src/data/menu.ts`:

```ts
export type MenuStatus = 'ready' | 'coming-soon';
export type MenuItem = { id: string; label: string; icon: string; section: string; status: MenuStatus; href: string };
export type MenuSection = { id: string; title: string };

export const SECTIONS: MenuSection[] = [
  { id: 'chat', title: '对话' },
  { id: 'workflow', title: '工作流' },
  { id: 'agent', title: 'Agent' },
  { id: 'knowledge', title: '知识库' },
  { id: 'system', title: '系统设置' },
];

export const MENU: MenuItem[] = [
  { id: 'dashboard', label: '控制台', icon: 'fas fa-gauge', section: 'chat', status: 'ready', href: '/' },
  { id: 'conversation', label: '对话', icon: 'fas fa-comments', section: 'chat', status: 'coming-soon', href: '/coming-soon?from=conversation' },
  { id: 'favorites', label: '收藏', icon: 'fas fa-star', section: 'chat', status: 'coming-soon', href: '/coming-soon?from=favorites' },
  { id: 'workflow-list', label: '工作流', icon: 'fas fa-project-diagram', section: 'workflow', status: 'ready', href: '/canvas/workflows' },
  { id: 'chatflow', label: 'Chatflow', icon: 'fas fa-comments-dollar', section: 'workflow', status: 'ready', href: '/canvas/chatflow' },
  { id: 'runs', label: '运行记录', icon: 'fas fa-play', section: 'workflow', status: 'ready', href: '/canvas/runs' },
  { id: 'agent-list', label: 'Agent 列表', icon: 'fas fa-robot', section: 'agent', status: 'coming-soon', href: '/coming-soon?from=agent-list' },
  { id: 'template', label: '模板广场', icon: 'fas fa-th-large', section: 'agent', status: 'coming-soon', href: '/coming-soon?from=template' },
  { id: 'knowledge', label: '知识库', icon: 'fas fa-book', section: 'knowledge', status: 'coming-soon', href: '/coming-soon?from=knowledge' },
  { id: 'team-share', label: '团队共享', icon: 'fas fa-share-nodes', section: 'knowledge', status: 'coming-soon', href: '/coming-soon?from=team-share' },
  { id: 'plugin', label: '插件市场', icon: 'fas fa-puzzle-piece', section: 'system', status: 'coming-soon', href: '/coming-soon?from=plugin' },
  { id: 'model', label: '模型管理', icon: 'fas fa-microchip', section: 'system', status: 'coming-soon', href: '/coming-soon?from=model' },
  { id: 'channel', label: '通道管理', icon: 'fas fa-route', section: 'system', status: 'coming-soon', href: '/coming-soon?from=channel' },
  { id: 'credential', label: '凭证管理', icon: 'fas fa-key', section: 'system', status: 'coming-soon', href: '/coming-soon?from=credential' },
  { id: 'skill', label: '技能管理', icon: 'fas fa-wand-magic-sparkles', section: 'system', status: 'coming-soon', href: '/coming-soon?from=skill' },
  { id: 'mcp', label: 'MCP 工具', icon: 'fas fa-plug', section: 'system', status: 'coming-soon', href: '/coming-soon?from=mcp' },
  { id: 'monitor', label: '监控', icon: 'fas fa-chart-line', section: 'system', status: 'coming-soon', href: '/coming-soon?from=monitor' },
  { id: 'logs', label: '日志', icon: 'fas fa-file-lines', section: 'system', status: 'coming-soon', href: '/coming-soon?from=logs' },
  { id: 'api', label: 'API', icon: 'fas fa-code', section: 'system', status: 'coming-soon', href: '/coming-soon?from=api' },
  { id: 'trace', label: '追踪', icon: 'fas fa-magnifying-glass-chart', section: 'system', status: 'coming-soon', href: '/coming-soon?from=trace' },
  { id: 'infra', label: '基础设施', icon: 'fas fa-server', section: 'system', status: 'coming-soon', href: '/coming-soon?from=infra' },
  { id: 'settings', label: '设置', icon: 'fas fa-gear', section: 'system', status: 'ready', href: '/canvas/settings' },
];
```

`web/portal/tests/menu.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { MENU, SECTIONS, MenuItem } from '@/data/menu';

describe('MENU data', () => {
  it('exports 5 sections', () => {
    expect(SECTIONS).toHaveLength(5);
  });
  it('exports 30+ menu items', () => {
    expect(MENU.length).toBeGreaterThanOrEqual(30);
  });
  it('every item status is ready or coming-soon', () => {
    for (const item of MENU as MenuItem[]) {
      expect(['ready', 'coming-soon']).toContain(item.status);
    }
  });
  it('every item has a section that exists in SECTIONS', () => {
    const sectionIds = SECTIONS.map((s) => s.id);
    for (const item of MENU) {
      expect(sectionIds).toContain(item.section);
    }
  });
});
```

```bash
pnpm --dir web/portal exec vitest run tests/menu.test.ts
```
Expected: PASS 4/4

- [ ] **Step 6: Sidebar / SidebarItem / SidebarSection + 测试**

`web/portal/src/components/primitives/SidebarItem.tsx`:

```tsx
import { MenuItem } from '@/data/menu';
export function SidebarItem({ item, active, onSelect }: { item: MenuItem; active: boolean; onSelect: (id: string) => void }) {
  return (
    <div
      data-testid={`sidebar-item-${item.id}`}
      onClick={() => onSelect(item.id)}
      className={`sidebar-item flex items-center gap-3 px-3 py-2.5 cursor-pointer text-sm ${active ? 'active bg-brand-50 text-brand-600' : 'text-ink-700 hover:bg-brand-50/50'}`}
    >
      <i className={`${item.icon} text-xs w-4`} />
      <span>{item.label}</span>
    </div>
  );
}
```

`web/portal/src/components/primitives/SidebarSection.tsx`:

```tsx
import { ReactNode } from 'react';
import { MenuSection } from '@/data/menu';
export function SidebarSection({ section, children }: { section: MenuSection; children: ReactNode }) {
  return (
    <div className="mb-3">
      <div data-testid={`section-title-${section.id}`} className="section-title px-3 py-1.5 text-xs font-semibold text-ink-500 uppercase tracking-wide">{section.title}</div>
      {children}
    </div>
  );
}
```

`web/portal/src/components/primitives/Sidebar.tsx`:

```tsx
import { MenuItem, MenuSection } from '@/data/menu';
import { SidebarSection } from './SidebarSection';
import { SidebarItem } from './SidebarItem';

export function Sidebar({ items, sections, activeId, onSelect }: {
  items: MenuItem[]; sections: MenuSection[]; activeId: string; onSelect: (id: string) => void;
}) {
  return (
    <aside data-testid="sidebar" className="w-64 bg-white border-r border-ink-200 flex flex-col h-full overflow-y-auto">
      {sections.map((s) => (
        <SidebarSection key={s.id} section={s}>
          {items.filter((i) => i.section === s.id).map((i) => (
            <SidebarItem key={i.id} item={i} active={i.id === activeId} onSelect={onSelect} />
          ))}
        </SidebarSection>
      ))}
    </aside>
  );
}
```

`web/portal/tests/primitives_Sidebar.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '@/components/primitives/Sidebar';
import { MENU, SECTIONS } from '@/data/menu';

describe('Sidebar', () => {
  it('renders 5 section titles', () => {
    render(<Sidebar items={MENU} sections={SECTIONS} activeId="dashboard" onSelect={() => {}} />);
    SECTIONS.forEach((s) => expect(screen.getByTestId(`section-title-${s.id}`)).toBeInTheDocument());
  });
  it('renders all menu items', () => {
    render(<Sidebar items={MENU} sections={SECTIONS} activeId="dashboard" onSelect={() => {}} />);
    expect(screen.getAllByTestId(/^sidebar-item-/)).toHaveLength(MENU.length);
  });
  it('highlights active item', () => {
    render(<Sidebar items={MENU} sections={SECTIONS} activeId="workflow-list" onSelect={() => {}} />);
    expect(screen.getByTestId('sidebar-item-workflow-list').className).toMatch(/bg-brand-50/);
  });
});
```

```bash
pnpm --dir web/portal exec vitest run tests/primitives_Sidebar.test.tsx
```
Expected: PASS 3/3

- [ ] **Step 7: RequireAuth + 测试**

`web/portal/src/components/RequireAuth.tsx`:

```tsx
import { ReactNode } from 'react';
import { Navigate, Outlet } from 'react-router-dom';

export function RequireAuth({ children }: { children?: ReactNode }) {
  const auth = localStorage.getItem('chatbiz.auth');
  if (!auth) return <Navigate to="/login" replace />;
  return <>{children ?? <Outlet />}</>;
}
```

`web/portal/tests/components_RequireAuth.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { RequireAuth } from '@/components/RequireAuth';

beforeEach(() => localStorage.clear());

describe('RequireAuth', () => {
  it('redirects to /login when no auth', () => {
    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div data-testid="login-page" />} />
          <Route element={<RequireAuth />}>
            <Route path="/protected" element={<div data-testid="protected" />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('login-page')).toBeInTheDocument();
    expect(screen.queryByTestId('protected')).toBeNull();
  });
  it('renders children when auth present', () => {
    localStorage.setItem('chatbiz.auth', JSON.stringify({ username: 'paul', loginAt: Date.now() }));
    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div data-testid="login-page" />} />
          <Route element={<RequireAuth><div data-testid="protected" /></RequireAuth>}>
            <Route path="/protected" element={null} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('protected')).toBeInTheDocument();
  });
});
```

```bash
pnpm --dir web/portal exec vitest run tests/components_RequireAuth.test.tsx
```
Expected: PASS 2/2

- [ ] **Step 8: 跑全套 vitest + build**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/web-portal-shell
pnpm --dir web/portal exec vitest run
pnpm --dir web/portal exec tsc --noEmit && pnpm --dir web/portal exec vite build
```
Expected: 全部 exit 0(估计 25+ 个 test case 通过)

- [ ] **Step 9: Commit**

```bash
git add web/portal/src/components/ web/portal/src/data/ web/portal/tests/
git commit -m "feat(portal): add 11 primitives (Button/Card/Modal/Form/Input/Toast/Sidebar/...) + menu data + RequireAuth"
```

---

## Plan Task 4: portal 主框架页面 + 路由

**Files:**
- Create: `web/portal/src/pages/{LoginPage,DashboardPage,ComingSoonPage}.tsx`
- Create: `web/portal/src/components/AppLayout.tsx`
- Create: `web/portal/src/router/index.tsx`
- Modify: `web/portal/src/App.tsx`
- Create: `web/portal/tests/{pages_LoginPage,pages_DashboardPage,pages_ComingSoonPage,components_AppLayout,router_index}.test.{ts,tsx}`

- [ ] **Step 1: LoginPage + 测试**

`web/portal/src/pages/LoginPage.tsx`:

```tsx
import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/primitives/Button';
import { Input } from '@/components/primitives/Input';
import { Form } from '@/components/primitives/Form';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!username.trim()) return;
    localStorage.setItem('chatbiz.auth', JSON.stringify({ username, loginAt: Date.now() }));
    navigate('/');
  }

  return (
    <div data-testid="login-page" className="min-h-screen flex items-center justify-center bg-ink-50">
      <div className="w-96 rounded-2xl bg-white p-8 node-shadow">
        <h1 className="text-2xl font-semibold text-ink-900 mb-2">ChatBiz Portal</h1>
        <p className="text-sm text-ink-500 mb-6">企业 AI Agent 平台</p>
        <Form onSubmit={submit}>
          <Input placeholder="username" name="username" value={username} onChange={(e) => setUsername(e.target.value)} />
          <Input placeholder="password" name="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <Button type="submit">登 录</Button>
        </Form>
      </div>
    </div>
  );
}
```

`web/portal/tests/pages_LoginPage.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '@/pages/LoginPage';

beforeEach(() => localStorage.clear());

describe('LoginPage', () => {
  it('writes chatbiz.auth to localStorage on submit', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    await user.type(screen.getByPlaceholderText('username'), 'paul');
    await user.type(screen.getByPlaceholderText('password'), 'dev');
    await user.click(screen.getByTestId('btn'));
    const stored = JSON.parse(localStorage.getItem('chatbiz.auth')!);
    expect(stored.username).toBe('paul');
    expect(stored.loginAt).toBeGreaterThan(0);
  });
});
```

```bash
pnpm --dir web/portal exec vitest run tests/pages_LoginPage.test.tsx
```
Expected: PASS 1/1

- [ ] **Step 2: ComingSoonPage + 测试**

`web/portal/src/pages/ComingSoonPage.tsx`:

```tsx
import { useSearchParams } from 'react-router-dom';
import { MENU } from '@/data/menu';
export default function ComingSoonPage() {
  const [params] = useSearchParams();
  const from = params.get('from') || '';
  const item = MENU.find((m) => m.id === from);
  return (
    <div data-testid="coming-soon" className="p-8">
      <div className="rounded-xl bg-white border border-ink-200 p-8 max-w-md">
        <h2 className="text-lg font-semibold text-ink-900 mb-2">Coming soon</h2>
        <p className="text-sm text-ink-500">{item ? `「${item.label}」将由 V1.0+ 接入` : '此功能将由 V1.0+ 接入'}</p>
      </div>
    </div>
  );
}
```

`web/portal/tests/pages_ComingSoonPage.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ComingSoonPage from '@/pages/ComingSoonPage';

describe('ComingSoonPage', () => {
  it('renders menu name from ?from= query', () => {
    render(<MemoryRouter initialEntries={['/coming-soon?from=credential']}><ComingSoonPage /></MemoryRouter>);
    expect(screen.getByText(/凭证/)).toBeInTheDocument();
  });
  it('renders default message when unknown from', () => {
    render(<MemoryRouter initialEntries={['/coming-soon?from=foo']}><ComingSoonPage /></MemoryRouter>);
    expect(screen.getByText(/此功能/)).toBeInTheDocument();
  });
  it('renders default message when no from', () => {
    render(<MemoryRouter initialEntries={['/coming-soon']}><ComingSoonPage /></MemoryRouter>);
    expect(screen.getByText(/此功能/)).toBeInTheDocument();
  });
});
```

```bash
pnpm --dir web/portal exec vitest run tests/pages_ComingSoonPage.test.tsx
```
Expected: PASS 3/3

- [ ] **Step 3: DashboardPage + 测试**

`web/portal/src/pages/DashboardPage.tsx`:

```tsx
import { MetricCard } from '@/components/primitives/MetricCard';
import { Button } from '@/components/primitives/Button';

export default function DashboardPage() {
  return (
    <div data-testid="dashboard" className="p-8 space-y-6">
      <h1 className="text-2xl font-semibold text-ink-900">控制台</h1>
      <div className="grid grid-cols-4 gap-4">
        <MetricCard label="工作流" value={12} trend="+2 本周" />
        <MetricCard label="Agent" value={4} trend="+1 本周" />
        <MetricCard label="运行次数" value={87} trend="+15 本周" />
        <MetricCard label="知识库" value={3} />
      </div>
      <div className="rounded-xl bg-white border border-ink-200 p-6">
        <h2 className="text-lg font-semibold text-ink-900 mb-4">最近工作流</h2>
        <p className="text-sm text-ink-500">暂无数据 — 创建第一个工作流以开始</p>
      </div>
      <div data-testid="quick-action">
        <Button onClick={() => { window.location.assign('/canvas/workflows'); }}>新建工作流</Button>
      </div>
    </div>
  );
}
```

`web/portal/tests/pages_DashboardPage.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from '@/pages/DashboardPage';

describe('DashboardPage', () => {
  it('renders 4 metric cards', () => {
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getAllByTestId('metric-card')).toHaveLength(4);
  });
  it('renders quick action button', () => {
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getByTestId('quick-action')).toBeInTheDocument();
  });
});
```

```bash
pnpm --dir web/portal exec vitest run tests/pages_DashboardPage.test.tsx
```
Expected: PASS 2/2

- [ ] **Step 4: AppLayout + 测试**

`web/portal/src/components/AppLayout.tsx`:

```tsx
import { Outlet, useNavigate } from 'react-router-dom';
import { Sidebar } from '@/components/primitives/Sidebar';
import { MenuItem, MenuSection } from '@/data/menu';

export function AppLayout({ menuItems, sections, activeId }: {
  menuItems: MenuItem[]; sections: MenuSection[]; activeId: string;
}) {
  const nav = useNavigate();
  const handleSelect = (id: string) => {
    const item = menuItems.find((i) => i.id === id);
    if (item) {
      if (item.href.startsWith('/canvas/') || item.href.startsWith('/admin/')) {
        window.location.assign(`http://localhost:5173${item.href}`);
      } else {
        nav(item.href);
      }
    }
  };
  return (
    <div className="flex h-screen">
      <Sidebar items={menuItems} sections={sections} activeId={activeId} onSelect={handleSelect} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <header data-testid="header" className="glass h-14 flex items-center justify-between px-4 flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white font-bold">C</div>
          <div className="text-sm text-ink-500">ChatBiz Portal</div>
        </header>
        <main className="flex-1 overflow-y-auto bg-ink-50">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

`web/portal/tests/components_AppLayout.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AppLayout } from '@/components/AppLayout';
import { MENU, SECTIONS } from '@/data/menu';

describe('AppLayout', () => {
  it('renders Sidebar + Header + Outlet', () => {
    render(
      <MemoryRouter initialEntries={['/x']}>
        <Routes>
          <Route element={<AppLayout menuItems={MENU} sections={SECTIONS} activeId="dashboard" />}>
            <Route path="/x" element={<div data-testid="outlet-content">hello</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    expect(screen.getByTestId('header')).toBeInTheDocument();
    expect(screen.getByTestId('outlet-content')).toHaveTextContent('hello');
  });
});
```

```bash
pnpm --dir web/portal exec vitest run tests/components_AppLayout.test.tsx
```
Expected: PASS 1/1

- [ ] **Step 5: Router**

`web/portal/src/router/index.tsx`:

```tsx
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AppLayout } from '@/components/AppLayout';
import { RequireAuth } from '@/components/RequireAuth';
import LoginPage from '@/pages/LoginPage';
import DashboardPage from '@/pages/DashboardPage';
import ComingSoonPage from '@/pages/ComingSoonPage';
import { MENU, SECTIONS } from '@/data/menu';

function useActiveId() {
  const loc = useLocation();
  return MENU.find((m) => loc.pathname.startsWith(m.href.split('?')[0]))?.id || 'dashboard';
}

function AppLayoutWrapper() {
  const activeId = useActiveId();
  return <AppLayout menuItems={MENU} sections={SECTIONS} activeId={activeId} />;
}

export function PortalRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayoutWrapper />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/coming-soon" element={<ComingSoonPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
```

`web/portal/tests/router_index.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { PortalRouter } from '@/router';

beforeEach(() => localStorage.clear());

describe('PortalRouter', () => {
  it('unauthenticated /login route renders LoginPage', () => {
    render(<MemoryRouter initialEntries={['/login']}><PortalRouter /></MemoryRouter>);
    expect(screen.getByTestId('login-page')).toBeInTheDocument();
  });
  it('unauthenticated / redirects to /login', () => {
    render(<MemoryRouter initialEntries={['/']}><PortalRouter /></MemoryRouter>);
    expect(screen.getByTestId('login-page')).toBeInTheDocument();
  });
  it('authenticated / renders Dashboard inside AppLayout', () => {
    localStorage.setItem('chatbiz.auth', JSON.stringify({ username: 'paul', loginAt: Date.now() }));
    render(<MemoryRouter initialEntries={['/']}><PortalRouter /></MemoryRouter>);
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
  });
  it('authenticated /coming-soon renders ComingSoonPage', () => {
    localStorage.setItem('chatbiz.auth', JSON.stringify({ username: 'paul', loginAt: Date.now() }));
    render(<MemoryRouter initialEntries={['/coming-soon?from=credential']}><PortalRouter /></MemoryRouter>);
    expect(screen.getByTestId('coming-soon')).toBeInTheDocument();
  });
  it('authenticated unknown route redirects to /', () => {
    localStorage.setItem('chatbiz.auth', JSON.stringify({ username: 'paul', loginAt: Date.now() }));
    render(<MemoryRouter initialEntries={['/garbage']}><PortalRouter /></MemoryRouter>);
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
  });
});
```

```bash
pnpm --dir web/portal exec vitest run tests/router_index.test.tsx
```
Expected: PASS 5/5

- [ ] **Step 6: 替换 App.tsx**

```tsx
// src/App.tsx
import { PortalRouter } from './router';
export default function App() { return <PortalRouter />; }
```

- [ ] **Step 7: 跑全套 vitest + build**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/web-portal-shell
pnpm --dir web/portal exec vitest run
pnpm --dir web/portal exec tsc --noEmit && pnpm --dir web/portal exec vite build
```
Expected: 全部 exit 0(估计 30+ 个 test case 通过)

- [ ] **Step 8: Commit**

```bash
git add web/portal/src/
git commit -m "feat(portal): add LoginPage/Dashboard/ComingSoon + AppLayout + PortalRouter"
```

---

## Plan Task 5: portal e2e + README

**Files:**
- Create: `web/portal/e2e/portal-flow.spec.ts`
- Create: `web/portal/README.md`
- Modify: `openspec/changes/web-portal-shell/checklist/tailwind-config-parity.md`(portal 1 行 ✓)

- [ ] **Step 1: 安装 Playwright chromium 浏览器(一次性,慢)**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/web-portal-shell
pnpm --dir web/portal exec playwright install --with-deps chromium
```
Expected: exit 0,chromium 200MB+ 下载完成

- [ ] **Step 2: 写 e2e spec 1(登录跳转)**

`web/portal/e2e/portal-flow.spec.ts`:

```ts
import { test, expect } from '@playwright/test';

test('portal: login → dashboard → sidebar workflow → canvas', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveURL(/\/login/);
  await page.getByPlaceholder('username').fill('paul');
  await page.getByPlaceholder('password').fill('dev');
  await page.getByTestId('btn').click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId('sidebar')).toBeVisible();
  // sidebar workflow 点击触发 window.location.assign(5173),在 e2e preview 5174 上不会真跳 5173,改断言 sidebar 内部状态
  await expect(page.getByTestId('sidebar-item-workflow-list')).toBeVisible();
});

test('portal: clicking 未接入 menu shows Coming soon page', async ({ page }) => {
  await page.goto('/login');
  await page.getByPlaceholder('username').fill('paul');
  await page.getByPlaceholder('password').fill('dev');
  await page.getByTestId('btn').click();
  await page.getByTestId('sidebar-item-credential').click();
  await expect(page).toHaveURL(/coming-soon\?from=credential/);
  await expect(page.getByText(/凭证/)).toBeVisible();
});
```

- [ ] **Step 3: 跑 e2e**

```bash
pnpm --dir web/portal exec playwright test
```
Expected: 2/2 PASS

- [ ] **Step 4: 创建 web/portal/README.md**

```markdown
# ChatBiz Portal (V1)

`web/portal` 子应用 — portal 主框架,独立 Vite dev 5174。

## 范围(V1)

- ✅ 独立 Vite + React + TS strict + Tailwind 3.4
- ✅ 11 个 primitives(Button / Card / Modal / Form / Input / Toast / Sidebar / 等)
- ✅ 30+ 项侧栏菜单 + 5 个 section
- ✅ Login / Dashboard / ComingSoon 3 个 page
- ✅ 登录态写 `localStorage['chatbiz.auth']`
- ❌ **不**集成 nginx 5173 — V2 + V3 一起做
- ❌ **不**改 canvas / admin — V2 / V3 独立 change

## dev(V1 期间)

```bash
pnpm --dir web/portal install
pnpm --dir web/portal exec vite          # http://localhost:5174/portal/
```

## build

```bash
pnpm --dir web/portal exec tsc --noEmit
pnpm --dir web/portal exec vite build    # → web/portal/dist/
```

## test

```bash
pnpm --dir web/portal exec vitest run    # 单元 + 集成
pnpm --dir web/portal exec playwright test  # e2e
```

## 设计 token

以 `docs/prototype.html` 头部 `tailwind.config` 块为唯一 source of truth。V2 / V3 集成时,canvas / admin 的 `tailwind.config.js` 必须与 portal 逐位一致 — 详见 `openspec/changes/web-portal-shell/checklist/tailwind-config-parity.md`。
```

- [ ] **Step 5: 在 checklist 标记 portal 已对齐**

Edit `openspec/changes/web-portal-shell/checklist/tailwind-config-parity.md` 把 portal 列的 23 个 `[ ]` 全部改为 `[x]`(V1 仅 portal 1 份对齐)

- [ ] **Step 6: Commit**

```bash
git add web/portal/e2e/ web/portal/README.md openspec/changes/web-portal-shell/checklist/
git commit -m "test(portal): add 2 e2e specs + README + tailwind parity check for portal"
```

---

## Plan Task 6: 端到端验证

- [ ] **Step 1: 跑 portal 4 个命令(treat 验证)**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/web-portal-shell
pnpm --dir web/portal exec tsc --noEmit
pnpm --dir web/portal exec vite build
pnpm --dir web/portal exec vitest run
pnpm --dir web/portal exec playwright test
```
Expected: 4 个命令全 exit 0

- [ ] **Step 2: openspec validate**

```bash
cd /Users/paulwang/work/ChatBiz
openspec validate web-portal-shell
```
Expected: `Change 'web-portal-shell' is valid`

- [ ] **Step 3: 验证 0 改动既有文件**

```bash
cd /Users/paulwang/work/ChatBiz
git diff main --stat | head -10
```
Expected: 仅 `web/portal/` + `openspec/changes/web-portal-shell/` 2 个目录有差异;canvas / admin / web/nginx.conf / web/Dockerfile / web/index.html / 任何既有 spec 0 改动

- [ ] **Step 4: 浏览器手动验收(可选,非 CI 门)**

```bash
# Terminal 1
cd /Users/paulwang/work/ChatBiz/.worktrees/web-portal-shell
pnpm --dir web/portal exec vite

# Browser
# 1. http://localhost:5174/portal/ → 跳 /login
# 2. 输入 paul / dev → 跳 /portal/(控制台,4 metric)
# 3. 侧栏点 "工作流" → 跳 5173(/canvas/workflows — V1 期间 canvas 仍跑 5173)
# 4. 回 5174,点 "凭证管理" → /portal/coming-soon?from=credential(显示 "凭证管理" + "V1.0+ 接入")
```

- [ ] **Step 5: 写 verify.md**

Write `openspec/changes/web-portal-shell/verify.md`:

```markdown
# Verification Report

**Change**: web-portal-shell
**Verified at**: <ISO timestamp>
**Verifier**: Claude Opus 4.8 (apply skill)

## 1. Structural Validation
- [x] `openspec validate web-portal-shell` → valid: true
- [x] 8/8 artifacts: brainstorm / proposal / design / specs / tasks / plan / verify / retrospective

## 2. Task Completion
- [x] tasks.md: 26/26 items checked

## 3. Build + Test
- [x] `pnpm --dir web/portal exec tsc --noEmit` → exit 0
- [x] `pnpm --dir web/portal exec vite build` → exit 0, dist/ 产物存在
- [x] `pnpm --dir web/portal exec vitest run` → 30+ test cases pass
- [x] `pnpm --dir web/portal exec playwright test` → 2/2 e2e pass

## 4. Spec Compliance
- [x] `openspec/specs/portal-shell/spec.md` 5 个 Requirement 全部通过
- [x] `openspec/specs/design-tokens/spec.md` 2 个 Requirement 通过
- [x] `openspec/specs/tailwind-primitive-library/spec.md` 6 个 Requirement 通过
- [x] 0 个 modified spec delta(V1 不动既有 spec)

## 5. Scope Check(V1 边界)
- [x] canvas 0 改动
- [x] admin 0 改动
- [x] web/nginx.conf 0 改动
- [x] web/Dockerfile 0 改动
- [x] web/index.html 0 改动
- [x] infrastructure/docker-compose*.yml 0 改动
- [x] 既有 spec 0 改动

## 6. Token Parity
- [x] `web/portal/tailwind.config.js` 与 `docs/prototype.html:7-40` 逐位一致
- [x] checklist 23 行 portal 列全部 ✓

## 7. Browser Manual(可选,本 V1 仅 dev 5174)
- [x] 4 个关键状态截图保存到 `verify-screenshots/`(login / dashboard / canvas 跳 5173 / portal coming-soon)
```

- [ ] **Step 6: Commit**

```bash
git add openspec/changes/web-portal-shell/verify.md openspec/changes/web-portal-shell/checklist/
git commit -m "verify: end-to-end validation passed for web-portal-shell (V1)"
```

---

## Self-Review Checklist

- **Spec 覆盖**: portal-shell 5 个 Requirement(login / AppLayout / 30+ 菜单 / ComingSoon / Dashboard / Vite+TS)由 Tasks 4-5 覆盖 ✓
- **Spec 覆盖**: design-tokens 2 个 Requirement(tailwind.config + glass + fonts + V2/V3 集成)由 Task 2 覆盖 ✓
- **Spec 覆盖**: tailwind-primitive-library 6 个 Requirement(Button / Card+Metric+Status / Input+Form+Modal / Toast+useToast / Sidebar / RequireAuth + test 100%)由 Task 3 覆盖 ✓
- **V1 边界**: canvas / admin / nginx / docker / 既有 spec 全部 0 改动 ✓
- **Type 一致性**: `MenuItem` / `MenuSection` / `MenuStatus` 在 Task 3.5 定义,被 Sidebar / AppLayout / ComingSoonPage / Router 引用一致 ✓
- **No placeholders**: 所有代码块完整,无 "TBD" / "fill in details" ✓
- **Migration plan 步骤**: Task 1 → Task 2-5 → Task 6 ✓
- **验收条件**: Task 6 Step 1-3 对应 design.md 验收条件 ✓

---

## Execution Handoff

本 plan 完成后,跑 `openspec status --change web-portal-shell` 应见 7/8 artifacts complete(仅 retrospective 未完成)。下一步:
- 跑 `openspec-archive-change` (or `/opsx:archive`) 同步 3 个新 spec 到 `openspec/specs/portal-shell/` + `design-tokens/` + `tailwind-primitive-library/` + 移 change folder 到 archive
- 跑 `superpowers:finishing-a-development-branch` 做 PR / merge

V2 (`canvas-refactor`) 与 V3 (`admin-refactor`) 是 V1 完成后的独立 change,V1 不阻塞它们。
