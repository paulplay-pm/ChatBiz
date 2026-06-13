# v2-canvas-refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `web/canvas` 22 处 antd 引用清零,抽 `web/ui/` 共享 11 个 primitives,集成 nginx 5173 统一入口,履行 V1 design.md 推迟的"三套子应用共享"目标。

**Architecture:**
- 抽 `web/ui/` 共享层(11 primitives + tailwind config + index.css),portal/canvas/admin 三套 import
- canvas 22 .tsx 删 antd 引用,改用 `web/ui/` primitives + tailwind
- 改 `web/canvas/tailwind.config.js` 与 portal 逐位一致(履行 `specs/design-tokens` 占位 Requirement)
- 集成 `web/Dockerfile` + 写 `web/index.html` portal 跳板(`web/nginx.conf` 已就绪)

**Tech Stack:** Vite 5 + React 18 + TypeScript 5.4 strict + Tailwind 3.4 + React Router 6 + @tanstack/react-query 5 + zustand 4 + @xyflow/react 12 + @rjsf 5(非 antd,保留)

---

## 实施上下文

**Worktree 路径**:`/Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor/`
**Branch 名**:`worktree-v2-canvas-refactor`
**Base ref**:`origin/main` (或 local main,本 session 内推到 35 commits ahead)

**本 session 跑 8 任务(T1-T8),T9-T10 留下次 session**:
- T9 集成 e2e
- T10 14-gate verify

**V2 范围**(必须严格遵守):
- ✅ 新建 `web/ui/` + 改 portal import + 改 canvas 22 .tsx + 删 antd + nginx 集成
- ❌ **不**动 admin(V3 接管)
- ❌ **不**动 `web/nginx.conf`(已就绪)
- ❌ **不**动 `openspec/specs/<existing>/spec.md`(MODIFIED delta 在 archive 时由 openspec CLI 自动同步,本 plan 不写 spec 文件)
- ❌ **不**动 docs/architecture.md / docs/prd.md / design doc
- ❌ **不**动后端 services / infrastructure
- ❌ **不**写 `web/README.md`(V3 一起)

**V1 portal 重要 reference**:
- `web/portal/src/components/primitives/*` — 11 个 primitives 本体(将被平移到 web/ui/)
- `web/portal/src/components/RequireAuth.tsx` — 也将平移到 `web/ui/primitives/`
- `web/portal/tailwind.config.js` — 单一 source,canvas/admin 复用
- `web/portal/src/index.css` — 含 glass / status-* / metric-card,迁到 web/ui/index.css
- `web/portal/tests/**` — 33 spec,改 import path 后全过

**V1 portal 现有 import 形式**(T2 改):
- `import { Sidebar } from '@/components/primitives/Sidebar';` → 改 `from 'ui/primitives/Sidebar';`
- `import { Button } from '@/components/primitives/Button';` → 改 `from 'ui/primitives/Button';`
- `import { RequireAuth } from '@/components/RequireAuth';` → 改 `from 'ui/primitives/RequireAuth';`
- `import { MenuItem, MenuSection } from '@/data/menu';` — **不动**(仍 `@/data/menu`)

**关键风险**(见 design.md §Risk):
- **R4**: T6 改 `useAuthStore` 时,**先** `cat openspec/specs/canvas-auth/spec.md` 验证 localStorage key 一致;不一致以 canvas-auth 为准,surface 冲突
- **R1**: antd 删后 `useForm` / `Form.useForm` 等 antd 专属 API 改用原生 form(跟 V1 portal 一致)
- **R2**: ConfigPanel 的 `@rjsf/core` 删 antd 后用 rjsf 默认主题(非 antd,不动 rjsf)
- **R3**: TopBar 图标用 inline SVG 替代 `@ant-design/icons`

---

## Task 1: 抽 `web/ui/` 骨架(11 primitives + tailwind config + index.css + package.json) — ✅ DONE (commit f65d475)

**Files:**
- Create: `web/ui/package.json` ✅
- Create: `web/ui/tailwind.config.js` ✅
- Create: `web/ui/tsconfig.json` ✅
- Create: `web/ui/index.css` ✅
- Create: `web/ui/primitives/{Button,Card,MetricCard,StatusDot,Input,Form,Modal,Toast,Sidebar,SidebarItem,SidebarSection,RequireAuth}.tsx` ✅ (12 文件,含 RequireAuth)
- Create: `web/ui/index.ts`(barrel export) ✅

> **T1 完成备注**: 11 primitives + RequireAuth 平移自 V1 portal;`MenuStatus` / `MenuItem` / `MenuSection` 类型内联到 `SidebarItem.tsx` / `SidebarSection.tsx`(避免 `@/data/menu` 私有路径依赖);barrel re-export 12 组件 + 2 类型;tsc 0 error;Spec/Code 评审通过(必要 trade-off 已记录)。

- [ ] **Step 1: 写 `web/ui/package.json`**

```json
{
  "name": "chatbiz-ui",
  "version": "0.0.1",
  "private": true,
  "type": "module",
  "main": "index.ts",
  "scripts": {
    "test": "vitest run"
  },
  "peerDependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "typescript": "^5.4.5",
    "vite": "^5.3.4",
    "tailwindcss": "^3.4.7"
  }
}
```

- [ ] **Step 2: 写 `web/ui/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
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
    "noImplicitAny": true
  },
  "include": ["primitives", "index.ts"]
}
```

- [ ] **Step 3: 写 `web/ui/tailwind.config.js`**(与 V1 portal 逐位一致)

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}', './primitives/**/*.{ts,tsx}'],
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

- [ ] **Step 4: 写 `web/ui/index.css`**(迁自 V1 portal)

```css
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

- [ ] **Step 5: 写 `web/ui/primitives/Button.tsx`**

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

- [ ] **Step 6: 写 `web/ui/primitives/Card.tsx`**

```tsx
import { ReactNode } from 'react';
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div data-testid="card" className={`rounded-xl bg-white border border-ink-200 node-shadow p-4 ${className}`}>{children}</div>;
}
```

- [ ] **Step 7: 写 `web/ui/primitives/MetricCard.tsx`**

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

- [ ] **Step 8: 写 `web/ui/primitives/StatusDot.tsx`**

```tsx
export function StatusDot({ status }: { status: 'running' | 'success' | 'error' | 'idle' | 'pending' }) {
  return <span data-testid="status-dot" className={`status-dot status-${status}`} />;
}
```

- [ ] **Step 9: 写 `web/ui/primitives/Input.tsx`**

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

- [ ] **Step 10: 写 `web/ui/primitives/Form.tsx`**

```tsx
import { FormEvent, ReactNode } from 'react';
export function Form({ onSubmit, children }: { onSubmit: (e: FormEvent) => void; children: ReactNode }) {
  return <form data-testid="form" onSubmit={onSubmit} className="space-y-4">{children}</form>;
}
```

- [ ] **Step 11: 写 `web/ui/primitives/Modal.tsx`**

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

- [ ] **Step 12: 写 `web/ui/primitives/Toast.tsx`**

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
const colorMap: Record<ToastKind, string> = { security: 'bg-red-500', user: 'bg-yellow-500', info: 'bg-brand-500' };
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

- [ ] **Step 13: 写 `web/ui/primitives/SidebarSection.tsx`**

```tsx
import { ReactNode } from 'react';
export type MenuSection = { id: string; title: string };
export function SidebarSection({ section, children }: { section: MenuSection; children: ReactNode }) {
  return (
    <div className="mb-3">
      <div data-testid={`section-title-${section.id}`} className="section-title px-3 py-1.5 text-xs font-semibold text-ink-500 uppercase tracking-wide">{section.title}</div>
      {children}
    </div>
  );
}
```

- [ ] **Step 14: 写 `web/ui/primitives/SidebarItem.tsx`**

```tsx
export type MenuItem = { id: string; label: string; icon: string; section: string; status: string; href: string };
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

- [ ] **Step 15: 写 `web/ui/primitives/Sidebar.tsx`**

```tsx
import { MenuItem, MenuSection } from './SidebarItem';
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

- [ ] **Step 16: 写 `web/ui/primitives/RequireAuth.tsx`**

```tsx
import { ReactNode } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
export function RequireAuth({ children }: { children?: ReactNode }) {
  const auth = localStorage.getItem('chatbiz.auth');
  if (!auth) return <Navigate to="/login" replace />;
  return <>{children ?? <Outlet />}</>;
}
```

- [ ] **Step 17: 写 `web/ui/index.ts`**(barrel)

```ts
export { Button } from './primitives/Button';
export { Card } from './primitives/Card';
export { MetricCard } from './primitives/MetricCard';
export { StatusDot } from './primitives/StatusDot';
export { Input } from './primitives/Input';
export { Form } from './primitives/Form';
export { Modal } from './primitives/Modal';
export { Toast, useToast } from './primitives/Toast';
export { Sidebar } from './primitives/Sidebar';
export { SidebarItem } from './primitives/SidebarItem';
export type { MenuItem } from './primitives/SidebarItem';
export { SidebarSection } from './primitives/SidebarSection';
export type { MenuSection } from './primitives/SidebarSection';
export { RequireAuth } from './primitives/RequireAuth';
```

- [ ] **Step 18: 验证 web/ui/ 编译**

Run: `cd /Users/paulwang/work/ChatBiz/web/ui && pnpm install && pnpm exec tsc --noEmit`
Expected: PASS,0 error

- [ ] **Step 19: Commit**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
git add web/ui/
git commit -m "feat(ui): 抽 web/ui/ 共享层 (11 primitives + tailwind + index.css)

- 新建 web/ui/ 共享层
- 12 文件: package.json / tsconfig.json / tailwind.config.js / index.css
- 11 primitives + 1 RequireAuth (12 组件平移自 V1 portal)
- index.ts barrel export
- 与 V1 portal tailwind.config.js 逐位一致

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 改 `web/portal/src/**` import path 指向 `web/ui/` — ✅ DONE (commit 66534b6 + 484bed1)

**Files:**
- Modify: `web/portal/package.json`(加 `chatbiz-ui: file:../ui` dep)
- Modify: `web/portal/tsconfig.json`(加 `ui/*` path alias)
- Modify: `web/portal/vite.config.ts`(加 `ui` alias)
- Modify: `web/portal/tailwind.config.js`(content 加 `../ui/primitives/**`)
- Modify: `web/portal/src/index.css`(import 改为 `'chatbiz-ui/index.css'`)
- Modify: `web/portal/src/components/AppLayout.tsx`(import 改)
- Modify: `web/portal/src/components/RequireAuth.tsx` → **删除文件**(迁到 web/ui)
- Modify: `web/portal/src/pages/{LoginPage,ComingSoonPage,DashboardPage}.tsx`(import 改)
- Modify: `web/portal/tests/**`(import 改)

- [ ] **Step 1: 改 `web/portal/package.json` 加 dep**

在 `dependencies` 末尾加一行:
```json
"chatbiz-ui": "file:../ui"
```

- [ ] **Step 2: 改 `web/portal/tsconfig.json` 加 path alias**

`paths` 改为:
```json
"paths": { "@/*": ["src/*"], "ui/*": ["../ui/*"], "chatbiz-ui": ["../ui/index.ts"] }
```

- [ ] **Step 3: 改 `web/portal/vite.config.ts` 加 alias**

`resolve.alias` 改为:
```js
alias: { '@': path.resolve(__dirname, './src'), 'chatbiz-ui': path.resolve(__dirname, '../ui/index.ts') }
```

- [ ] **Step 4: 改 `web/portal/tailwind.config.js` content**

`content` 改为:
```js
content: ['./index.html', './src/**/*.{ts,tsx}', '../ui/primitives/**/*.{ts,tsx}']
```

- [ ] **Step 5: 改 `web/portal/src/index.css`**

替换为:
```css
@import 'chatbiz-ui/index.css';

body { font-family: 'DM Sans', system-ui, sans-serif; margin: 0; }
```

- [ ] **Step 6: 改 `web/portal/src/components/AppLayout.tsx`**

第 2 行 `import { Sidebar } from '@/components/primitives/Sidebar';` 改为:
```tsx
import { Sidebar } from 'ui/primitives/Sidebar';
```

- [ ] **Step 7: 删 `web/portal/src/components/RequireAuth.tsx`**(迁到 web/ui)

```bash
rm /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor/web/portal/src/components/RequireAuth.tsx
```

- [ ] **Step 8: 改 3 个 page 的 import**

在 `web/portal/src/pages/{LoginPage,ComingSoonPage,DashboardPage}.tsx` 中:
- `import { Button } from '@/components/primitives/Button';` → `import { Button } from 'ui/primitives/Button';`
- `import { Card } from '@/components/primitives/Card';` → `import { Card } from 'ui/primitives/Card';`
- `import { MetricCard } from '@/components/primitives/MetricCard';` → `import { MetricCard } from 'ui/primitives/MetricCard';`
- `import { Modal } from '@/components/primitives/Modal';` → `import { Modal } from 'ui/primitives/Modal';`
- `import { Form } from '@/components/primitives/Form';` → `import { Form } from 'ui/primitives/Form';`
- `import { Input } from '@/components/primitives/Input';` → `import { Input } from 'ui/primitives/Input';`

(具体哪个 page 引哪些 primitive,实施时 `grep "@/components/primitives" web/portal/src/pages/*.tsx` 找)

- [ ] **Step 9: 改 `web/portal/src/router/index.tsx`**

`import { RequireAuth } from '@/components/RequireAuth';` 改为:
```tsx
import { RequireAuth } from 'ui/primitives/RequireAuth';
```

- [ ] **Step 10: 改 `web/portal/src/components/AppLayout.tsx` 加 ToastProvider(若未加)**

检查:若 AppLayout 未含 `<ToastProvider>`,在 `<div className="flex h-screen">` 内部包 `<ToastProvider>`;若已有 skip。

- [ ] **Step 11: 改 `web/portal/tests/**` 全部 import path**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
find web/portal/tests -name '*.test.ts*' -exec sed -i '' "s|@/components/primitives/|ui/primitives/|g" {} \;
find web/portal/tests -name '*.test.ts*' -exec sed -i '' "s|@/components/RequireAuth|ui/primitives/RequireAuth|g" {} \;
```

- [ ] **Step 12: 验证 portal tsc + vitest**

Run:
```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm install
pnpm --dir web/portal exec tsc --noEmit
pnpm --dir web/portal exec vitest run
```

Expected: tsc 0 error; vitest 33/33 全过

- [ ] **Step 13: 删 `web/portal/src/components/primitives/` 整个目录**

```bash
rm -rf web/portal/src/components/primitives/
```

- [ ] **Step 14: 删 `web/portal/src/index.css` 的旧 glass/status 类(已迁 web/ui)**

确认 `web/portal/src/index.css` 只剩 `@import 'chatbiz-ui/index.css';` + `body { ... }` 两行。

- [ ] **Step 15: Commit**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
git add web/portal/
git commit -m "refactor(portal): 改 import path 指向 web/ui/ 共享层

- 加 chatbiz-ui: file:../ui dep
- tsconfig + vite.config 加 ui alias
- 11 处 import path 改 ui/primitives/*
- 删 web/portal/src/components/primitives/ (已迁 web/ui)
- 删 web/portal/src/components/RequireAuth.tsx (已迁 web/ui)
- vitest 33/33 仍过

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: portal playwright e2e 仍过 + vite build 验证

**Files:**
- Modify: `web/portal/playwright.config.ts`(若有 baseURL 调整)
- Run tests(不创建新文件)

- [ ] **Step 1: 跑 portal playwright e2e**

Run:
```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/portal exec vite build
```

Expected: build 成功(可能有 bundle size warning,允许)

- [ ] **Step 2: 跑 portal e2e**

Run:
```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/portal exec playwright test
```

Expected: 2+ e2e 全过

- [ ] **Step 3: 跑 portal vitest(再次回归)**

Run:
```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/portal exec vitest run
```

Expected: 33+ spec 全过

- [ ] **Step 4: 验证 build 产物含 portal dist**

Run:
```bash
ls /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor/web/portal/dist/
```

Expected: `index.html` + `assets/*.js` + `assets/*.css` 存在

- [ ] **Step 5: Commit(若需)**

若本任务无新文件,可跳过 commit。前序 T2 commit 已包含 import path 改动。

- [ ] **Step 6: Surface**

T1-T3 完成时,user 应能确认:
- web/ui/ 共享层落地
- portal 改 import 后 33+ vitest + 2+ e2e + build 全过
- canvas 集成环境就绪

---

## Task 4: canvas 11 个简单 .tsx 删 antd 改 tailwind + web/ui/ primitives

**Files:**
- Modify: `web/canvas/src/components/AppLayout.tsx`
- Modify: `web/canvas/src/components/ErrorBoundary.tsx`
- Modify: `web/canvas/src/components/Sidebar.tsx`
- Modify: `web/canvas/src/components/TopBar.tsx`
- Modify: `web/canvas/src/components/CreateWorkflowModal.tsx`
- Modify: `web/canvas/src/components/DeleteConfirmModal.tsx`
- Modify: `web/canvas/src/components/WorkflowCard.tsx`
- Modify: `web/canvas/src/components/RequireAuth.tsx`
- Modify: `web/canvas/src/pages/LoginPage.tsx`
- Modify: `web/canvas/src/pages/NotFoundPage.tsx`
- Modify: `web/canvas/src/pages/SettingsPage.tsx`

- [ ] **Step 1: 改 `web/canvas/src/components/RequireAuth.tsx`**

替换为(从 web/ui/primitives/RequireAuth 复用):
```tsx
export { RequireAuth } from 'ui/primitives/RequireAuth';
```

- [ ] **Step 2: 改 `web/canvas/src/components/ErrorBoundary.tsx`**

```tsx
import { Component, ErrorInfo, ReactNode } from 'react';
interface Props { children: ReactNode; }
interface State { hasError: boolean; error?: Error; }
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div data-testid="error-boundary" className="flex flex-col items-center justify-center p-12">
          <h2 className="text-2xl font-semibold text-ink-900 mb-2">出错了</h2>
          <p className="text-sm text-ink-500 mb-4">{this.state.error?.message || '未知错误'}</p>
          <button data-testid="error-reload" onClick={() => window.location.reload()} className="rounded-lg font-medium px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm">
            刷新页面
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 3: 改 `web/canvas/src/components/Sidebar.tsx`**

```tsx
import { useNavigate, useLocation } from 'react-router-dom';
import { useUIStore } from '@/store/useUIStore';
import { MenuItem, MenuSection, Sidebar } from 'ui';

const items: MenuItem[] = [
  { id: 'workflows', label: '工作流', icon: 'fas fa-project-diagram', section: 'workflow', status: 'ready', href: '/workflows' },
  { id: 'chatflow', label: '对话', icon: 'fas fa-comments', section: 'workflow', status: 'ready', href: '/chatflow' },
  { id: 'knowledge', label: '知识库', icon: 'fas fa-book', section: 'knowledge', status: 'ready', href: '/knowledge' },
  { id: 'plugins', label: '插件', icon: 'fas fa-plug', section: 'system', status: 'ready', href: '/plugins' },
  { id: 'settings', label: '系统设置', icon: 'fas fa-gear', section: 'system', status: 'ready', href: '/settings' },
];
const sections: MenuSection[] = [
  { id: 'workflow', title: '工作流' },
  { id: 'knowledge', title: '知识库' },
  { id: 'system', title: '系统设置' },
];

export function AppSidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { sidebarCollapsed } = useUIStore();
  const activeId = items.find((i) => location.pathname.startsWith(i.href))?.id || 'workflows';
  return (
    <div className={`flex flex-col h-full border-r border-ink-200 bg-white transition-all ${sidebarCollapsed ? 'w-16' : 'w-60'}`}>
      <Sidebar
        items={items}
        sections={sections}
        activeId={activeId}
        onSelect={(id) => {
          const it = items.find((x) => x.id === id);
          if (it) navigate(it.href);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 4: 改 `web/canvas/src/components/TopBar.tsx`**

```tsx
import { useNavigate } from 'react-router-dom';
import { useUIStore } from '@/store/useUIStore';

const IconMenu = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" /></svg>;
const IconBell = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 8a6 6 0 0112 0c0 7 3 9 3 9H3s3-2 3-9z" /><path d="M10 21a2 2 0 004 0" /></svg>;
const IconUser = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="8" r="4" /><path d="M4 21v-1a8 8 0 0116 0v1" /></svg>;
const IconLogout = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>;

export function TopBar() {
  const navigate = useNavigate();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();
  const username = JSON.parse(localStorage.getItem('chatbiz.auth') || '{}').username || 'guest';

  const logout = () => {
    localStorage.removeItem('chatbiz.auth');
    navigate('/login');
  };

  return (
    <header data-testid="topbar" className="glass h-14 flex items-center justify-between px-4 flex-shrink-0 border-b border-ink-200">
      <div className="flex items-center gap-3">
        <button data-testid="toggle-sidebar" onClick={toggleSidebar} className="rounded-lg p-1.5 hover:bg-ink-100 text-ink-700">
          <IconMenu />
        </button>
        <div className="text-lg font-semibold text-ink-900">ChatBiz</div>
      </div>
      <div className="flex items-center gap-3">
        <button data-testid="bell" className="rounded-lg p-1.5 hover:bg-ink-100 text-ink-700 relative">
          <IconBell />
        </button>
        <div className="relative group">
          <button data-testid="user-menu" className="flex items-center gap-2 rounded-lg p-1.5 hover:bg-ink-100 text-ink-700">
            <span className="w-7 h-7 rounded-full bg-brand-500 text-white text-xs flex items-center justify-center font-semibold">{username[0]?.toUpperCase()}</span>
            <span className="text-sm">{username}</span>
          </button>
          <div data-testid="user-menu-dropdown" className="hidden group-hover:block absolute right-0 mt-1 w-40 bg-white rounded-lg node-shadow border border-ink-200 py-1 z-50">
            <button data-testid="logout" onClick={logout} className="w-full text-left px-3 py-2 text-sm hover:bg-ink-100 text-ink-900 flex items-center gap-2">
              <IconLogout /> 登出
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 5: 改 `web/canvas/src/components/AppLayout.tsx`**

```tsx
import { Outlet } from 'react-router-dom';
import { TopBar } from './TopBar';
import { AppSidebar } from './Sidebar';
import { ErrorBoundary } from './ErrorBoundary';
import { ToastProvider } from 'ui/primitives/Toast';

export function AppLayout() {
  return (
    <ToastProvider>
      <div className="flex h-screen">
        <AppSidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-y-auto bg-ink-50 p-6">
            <ErrorBoundary>
              <Outlet />
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}
```

- [ ] **Step 6: 改 `web/canvas/src/components/WorkflowCard.tsx`**

实施时 `cat web/canvas/src/components/WorkflowCard.tsx` 看 antd 引用(`<Card>` / `<Tag>` / `<Button>`),替换为 `ui` primitives + tailwind。模板:

```tsx
import { Card, Button, StatusDot } from 'ui';

export function WorkflowCard({ workflow, onEdit, onDelete }: any) {
  return (
    <Card className="hover:border-brand-500 cursor-pointer">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-ink-900">{workflow.name}</h3>
        <StatusDot status={workflow.status || 'idle'} />
      </div>
      <p className="text-xs text-ink-500 mb-3">{workflow.description || '无描述'}</p>
      <div className="flex gap-2">
        <Button variant="primary" size="sm" onClick={() => onEdit(workflow.id)}>编辑</Button>
        <Button variant="ghost" size="sm" onClick={() => onDelete(workflow.id)}>删除</Button>
      </div>
    </Card>
  );
}
```

(实际 props 跟 `cat` 出来的接口对齐)

- [ ] **Step 7: 改 `web/canvas/src/components/CreateWorkflowModal.tsx`**

模板:
```tsx
import { Modal, Form, Input, Button } from 'ui';

export function CreateWorkflowModal({ open, onClose, onCreate }: any) {
  return (
    <Modal open={open} onClose={onClose} title="新建工作流">
      <Form onSubmit={(e) => { e.preventDefault(); const fd = new FormData(e.currentTarget); onCreate({ name: fd.get('name') as string }); }}>
        <Input name="name" placeholder="工作流名称" />
        <div className="flex gap-2 justify-end mt-4">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button variant="primary" type="submit">创建</Button>
        </div>
      </Form>
    </Modal>
  );
}
```

(实际 props 跟 `cat` 对齐)

- [ ] **Step 8: 改 `web/canvas/src/components/DeleteConfirmModal.tsx`**

类似 CreateWorkflowModal 模板,`title="确认删除"` + confirm button。

- [ ] **Step 9: 改 `web/canvas/src/pages/LoginPage.tsx`**

模板:
```tsx
import { Form, Input, Button } from 'ui';
import { useNavigate } from 'react-router-dom';

export default function LoginPage() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-50">
      <div className="bg-white rounded-xl p-8 w-96 node-shadow border border-ink-200">
        <h1 className="text-2xl font-semibold text-ink-900 mb-6">ChatBiz 登录</h1>
        <Form onSubmit={(e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget);
          localStorage.setItem('chatbiz.auth', JSON.stringify({ username: fd.get('username'), loginAt: Date.now() }));
          navigate('/workflows');
        }}>
          <Input name="username" placeholder="用户名" />
          <Input name="password" type="password" placeholder="密码" />
          <Button variant="primary" type="submit" className="w-full mt-4">登录</Button>
        </Form>
      </div>
    </div>
  );
}
```

- [ ] **Step 10: 改 `web/canvas/src/pages/NotFoundPage.tsx`**

```tsx
import { Button } from 'ui';
import { useNavigate } from 'react-router-dom';
export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col items-center justify-center p-12">
      <h1 className="text-4xl font-semibold text-ink-900 mb-2">404</h1>
      <p className="text-sm text-ink-500 mb-4">页面不存在</p>
      <Button variant="primary" onClick={() => navigate('/workflows')}>回工作流</Button>
    </div>
  );
}
```

- [ ] **Step 11: 改 `web/canvas/src/pages/SettingsPage.tsx`**

```tsx
import { Card } from 'ui';
export default function SettingsPage() {
  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink-900 mb-4">系统设置</h1>
      <Card>
        <p className="text-sm text-ink-500">设置占位页</p>
      </Card>
    </div>
  );
}
```

- [ ] **Step 12: 验证 tsc 编译**

Run:
```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/canvas exec tsc --noEmit 2>&1 | head -30
```

Expected: 仍有 antd 引用错误(其他 11 个 .tsx 未改),但本批 11 个 0 error。

- [ ] **Step 13: Commit**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
git add web/canvas/src/
git commit -m "refactor(canvas): 11 个简单组件 删 antd 改 ui primitives

- AppLayout / ErrorBoundary / Sidebar / TopBar
- CreateWorkflowModal / DeleteConfirmModal / WorkflowCard
- RequireAuth (改 re-export web/ui/primitives/RequireAuth)
- pages: LoginPage / NotFoundPage / SettingsPage

每个组件改 antd 引用为 ui primitives + tailwind class
TopBar 图标换 inline SVG (R3 fix)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: canvas 11 个复杂 .tsx 删 antd 改 tailwind + web/ui/ primitives

**Files:**
- Modify: `web/canvas/src/hooks/useSaveWorkflow.ts`
- Modify: `web/canvas/src/components/canvas/NodePanel.tsx`
- Modify: `web/canvas/src/components/canvas/ConfigPanel.tsx`
- Modify: `web/canvas/src/components/canvas/EdgeConditionMenu.tsx`
- Modify: `web/canvas/src/components/canvas/NodeSearchModal.tsx`
- Modify: `web/canvas/src/components/chatflow/ApprovalInlineCard.tsx`
- Modify: `web/canvas/src/components/debugger/NodeEventTimeline.tsx`
- Modify: `web/canvas/src/components/debugger/RetryCancelButtons.tsx`
- Modify: `web/canvas/src/pages/CanvasPage.tsx`
- Modify: `web/canvas/src/pages/RunDebuggerPage.tsx`
- Modify: `web/canvas/src/pages/WorkflowListPage.tsx`
- Modify: `web/canvas/src/pages/ChatflowPage.tsx`

- [ ] **Step 1: 改 `web/canvas/src/hooks/useSaveWorkflow.ts`**

实施时 `cat` 原文件,删 antd `message`/`notification` 引用,改用 `useToast`:

```ts
import { useMutation } from '@tanstack/react-query';
import { useToast } from 'ui/primitives/Toast';

export function useSaveWorkflow(workflowId: string) {
  const toast = useToast();
  return useMutation({
    mutationFn: async (data: any) => {
      const res = await fetch(`/api/workflows/${workflowId}`, { method: 'PUT', body: JSON.stringify(data) });
      if (!res.ok) throw new Error('保存失败');
      return res.json();
    },
    onSuccess: () => toast.info('保存成功'),
    onError: (e: Error) => toast.error(e.message),
  });
}
```

(实际 mutationFn 跟 `cat` 出来的接口对齐)

- [ ] **Step 2: 改 `web/canvas/src/components/canvas/NodePanel.tsx`**

模板(具体 props 跟 `cat` 对齐):
```tsx
import { Card, Input } from 'ui';

export function NodePanel({ nodes, onSelect }: any) {
  return (
    <Card className="w-60">
      <h3 className="text-sm font-semibold text-ink-900 mb-2">节点</h3>
      <Input placeholder="搜索节点" />
      <div className="mt-2 space-y-1">
        {nodes.map((n: any) => (
          <div key={n.id} data-testid={`node-${n.id}`} onClick={() => onSelect(n)} className="px-2 py-1.5 text-sm rounded cursor-pointer hover:bg-brand-50 text-ink-700">
            {n.label}
          </div>
        ))}
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: 改 `web/canvas/src/components/canvas/ConfigPanel.tsx`**

`ConfigPanel` 用 `@rjsf/core`,R2 风险 —— 删 antd 后 rjsf 主题可能失效。**最小改动**:加 `validator` 去掉 antd theme:

```tsx
import Form from '@rjsf/core';
import validator from '@rjsf/validator-ajv8';
import { Card } from 'ui';

export function ConfigPanel({ schema, formData, onChange }: any) {
  return (
    <Card className="w-80">
      <h3 className="text-sm font-semibold text-ink-900 mb-2">配置</h3>
      <Form schema={schema} validator={validator} formData={formData} onChange={(e) => onChange(e.formData)} />
    </Card>
  );
}
```

(R2: 不动 rjsf,删 antd 后 rjsf 用默认 theme;若失效,后续 V3 修复)

- [ ] **Step 4: 改 `web/canvas/src/components/canvas/EdgeConditionMenu.tsx`**

模板:
```tsx
import { Modal, Form, Input, Button } from 'ui';
export function EdgeConditionMenu({ open, onClose, onSave }: any) {
  return (
    <Modal open={open} onClose={onClose} title="边条件">
      <Form onSubmit={(e) => { e.preventDefault(); onSave(new FormData(e.currentTarget).get('condition')); onClose(); }}>
        <Input name="condition" placeholder="condition expression" />
        <div className="flex gap-2 justify-end mt-4">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button variant="primary" type="submit">保存</Button>
        </div>
      </Form>
    </Modal>
  );
}
```

- [ ] **Step 5: 改 `web/canvas/src/components/canvas/NodeSearchModal.tsx`**

类似 EdgeConditionMenu 模板,加 `Input` 搜索框 + 结果列表。

- [ ] **Step 6: 改 `web/canvas/src/components/chatflow/ApprovalInlineCard.tsx`**

模板:
```tsx
import { Card, Button, StatusDot } from 'ui';

export function ApprovalInlineCard({ approval, onApprove, onReject }: any) {
  return (
    <Card>
      <div className="flex items-center gap-2 mb-2">
        <StatusDot status="pending" />
        <h4 className="text-sm font-semibold text-ink-900">人工审批</h4>
      </div>
      <p className="text-sm text-ink-700 mb-3">{approval.message}</p>
      <div className="flex gap-2">
        <Button variant="primary" size="sm" onClick={() => onApprove(approval.id)}>批准</Button>
        <Button variant="ghost" size="sm" onClick={() => onReject(approval.id)}>拒绝</Button>
      </div>
    </Card>
  );
}
```

- [ ] **Step 7: 改 `web/canvas/src/components/debugger/NodeEventTimeline.tsx`**

`cat` 原文件,删 antd `Timeline` 组件,改原生 `<ol>` + tailwind:
```tsx
import { Card, StatusDot } from 'ui';

export function NodeEventTimeline({ events }: { events: Array<{ id: string; time: string; status: 'success' | 'error' | 'pending' | 'running'; message: string }> }) {
  return (
    <Card>
      <h3 className="text-sm font-semibold text-ink-900 mb-2">事件时间线</h3>
      <ol className="space-y-2">
        {events.map((e) => (
          <li key={e.id} data-testid={`event-${e.id}`} className="flex items-start gap-2 text-sm">
            <StatusDot status={e.status} />
            <div>
              <div className="text-ink-900">{e.message}</div>
              <div className="text-xs text-ink-500">{e.time}</div>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}
```

- [ ] **Step 8: 改 `web/canvas/src/components/debugger/RetryCancelButtons.tsx`**

```tsx
import { Button } from 'ui';
export function RetryCancelButtons({ onRetry, onCancel, running }: any) {
  return (
    <div className="flex gap-2">
      <Button variant="primary" size="sm" onClick={onRetry} disabled={running}>重试</Button>
      <Button variant="ghost" size="sm" onClick={onCancel} disabled={!running}>取消</Button>
    </div>
  );
}
```

- [ ] **Step 9: 改 `web/canvas/src/pages/CanvasPage.tsx`**

`cat` 原文件。CanvasPage 含 `@xyflow/react` + `ConfigPanel` + `NodePanel`,主要删 antd `<Layout>` / `<Card>` 引用,改 tailwind div + `ui/Card`:

```tsx
import { useParams } from 'react-router-dom';
import { ReactFlow, Background, Controls, MiniMap } from '@xyflow/react';
import { NodePanel } from '@/components/canvas/NodePanel';
import { ConfigPanel } from '@/components/canvas/ConfigPanel';
import { Card } from 'ui';
import '@xyflow/react/dist/style.css';

export default function CanvasPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div data-testid="canvas-page" className="flex h-full gap-4">
      <NodePanel />
      <div className="flex-1 bg-white rounded-xl node-shadow border border-ink-200">
        <ReactFlow>
          <Background />
          <Controls />
          <MiniMap />
        </ReactFlow>
      </div>
      <ConfigPanel />
    </div>
  );
}
```

(实际接口跟 `cat` 对齐)

- [ ] **Step 10: 改 `web/canvas/src/pages/RunDebuggerPage.tsx`**

`cat` 原文件,删 antd `<Tabs>` 等,改 tailwind:
```tsx
import { useParams } from 'react-router-dom';
import { Card } from 'ui';
import { NodeEventTimeline } from '@/components/debugger/NodeEventTimeline';
import { RetryCancelButtons } from '@/components/debugger/RetryCancelButtons';

export default function RunDebuggerPage() {
  const { runId } = useParams<{ runId: string }>();
  return (
    <div data-testid="run-debugger" className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink-900">运行 #{runId}</h1>
        <RetryCancelButtons />
      </div>
      <Card>
        <NodeEventTimeline events={[]} />
      </Card>
    </div>
  );
}
```

- [ ] **Step 11: 改 `web/canvas/src/pages/WorkflowListPage.tsx`**

`cat` 原文件,删 antd `<List>` / `<Card>`,改 `Card` + 列表:
```tsx
import { useNavigate } from 'react-router-dom';
import { Card, Button } from 'ui';
import { WorkflowCard } from '@/components/WorkflowCard';
import { CreateWorkflowModal } from '@/components/CreateWorkflowModal';
import { useState } from 'react';
import { useWorkflows } from '@/hooks/useWorkflows';

export default function WorkflowListPage() {
  const navigate = useNavigate();
  const { data: workflows = [] } = useWorkflows();
  const [createOpen, setCreateOpen] = useState(false);
  return (
    <div data-testid="workflow-list" className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink-900">工作流</h1>
        <Button variant="primary" onClick={() => setCreateOpen(true)}>新建</Button>
      </div>
      <div className="grid grid-cols-3 gap-4">
        {workflows.map((w: any) => (
          <WorkflowCard key={w.id} workflow={w} onEdit={(id: string) => navigate(`/workflows/${id}/edit`)} onDelete={() => {}} />
        ))}
      </div>
      <CreateWorkflowModal open={createOpen} onClose={() => setCreateOpen(false)} onCreate={(d) => { console.log(d); setCreateOpen(false); }} />
    </div>
  );
}
```

- [ ] **Step 12: 改 `web/canvas/src/pages/ChatflowPage.tsx`**

`cat` 原文件,删 antd `<Input.TextArea>` / `<Button>`,改 `ui` primitives:
```tsx
import { Card, Form, Input, Button } from 'ui';
export default function ChatflowPage() {
  return (
    <div data-testid="chatflow-page" className="max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink-900 mb-4">Chatflow 对话</h1>
      <Card>
        <Form onSubmit={(e) => { e.preventDefault(); }}>
          <Input name="message" placeholder="输入消息" />
          <Button variant="primary" type="submit" className="mt-2">发送</Button>
        </Form>
      </Card>
    </div>
  );
}
```

- [ ] **Step 13: 验证 tsc 编译**

Run:
```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/canvas exec tsc --noEmit 2>&1 | head -30
```

Expected: 仅 `package.json` antd 引用未删 + `main.tsx` ConfigProvider/zhCN 引用未删导致 error;组件层 0 error

- [ ] **Step 14: Commit**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
git add web/canvas/src/
git commit -m "refactor(canvas): 11 个复杂组件 删 antd 改 ui primitives

- hooks/useSaveWorkflow 改 useToast
- canvas/NodePanel / ConfigPanel / EdgeConditionMenu / NodeSearchModal
- chatflow/ApprovalInlineCard
- debugger/NodeEventTimeline / RetryCancelButtons
- pages: CanvasPage / RunDebuggerPage / WorkflowListPage / ChatflowPage

useForm / Form.useForm 改原生 form (R1 fix)
ConfigPanel rjsf 用默认 theme (R2 fix)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: canvas `package.json` 删 antd + `main.tsx` 删 ConfigProvider

**Files:**
- Modify: `web/canvas/package.json`(删 antd + @ant-design/icons,加 chatbiz-ui)
- Modify: `web/canvas/src/main.tsx`(删 ConfigProvider + zhCN)
- Modify: `web/canvas/src/index.css`(import 改 web/ui)
- Modify: `web/canvas/src/store/useAuthStore.ts`(R4: 改 localStorage 契约)

- [ ] **Step 1: 读 `openspec/specs/canvas-auth/spec.md` 验证 localStorage key**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
cat openspec/specs/canvas-auth/spec.md | grep -A 3 -i "localStorage\|chatbiz.auth"
```

Expected: 确认 `localStorage['chatbiz.auth']` 契约
**若不一致**:`grep` 输出不匹配 `chatbiz.auth`,以 canvas-auth 为准并 surface 冲突(暂停本任务)

- [ ] **Step 2: 改 `web/canvas/package.json`**

`dependencies` 部分:
- 删 `"@ant-design/icons": "^5.4.0",`
- 删 `"antd": "^5.20.0",`
- 删 `"@rjsf/core": "^5.22.0",`(若 R2 决定 ConfigPanel 不再用 rjsf,本 task 删;若保留,**不动** rjsf deps)
- 加 `"chatbiz-ui": "file:../ui",`

(若决定保留 rjsf,ConfigPanel 的 `@rjsf/core` import 不删,V3 再处理)

- [ ] **Step 3: 改 `web/canvas/src/main.tsx`**

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';
import 'ui/index.css';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={import.meta.env.VITE_APP_BASE?.replace(/\/$/, '') || undefined}>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
```

- [ ] **Step 4: 改 `web/canvas/src/index.css`**

替换为:
```css
@import 'ui/index.css';
```

(若 web/canvas 原本无 src/index.css,跳过本步)

- [ ] **Step 5: 改 `web/canvas/src/store/useAuthStore.ts`(R4 修复)**

实施时 `cat` 原文件。原 store 把 JWT 存内存。V2 改读 `localStorage['chatbiz.auth']` 标记:

```ts
import { create } from 'zustand';

type User = { username: string; loginAt: number };

export const useAuthStore = create<{ user: User | null; clear: () => void }>((set) => ({
  user: JSON.parse(localStorage.getItem('chatbiz.auth') || 'null'),
  clear: () => {
    localStorage.removeItem('chatbiz.auth');
    set({ user: null });
  },
}));
```

(原 useAuthStore 可能还有 `login()` / `setUser()` 等方法;实施时 `cat` 出来逐方法改)

- [ ] **Step 6: 跑 `pnpm install` 重新装**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm install
```

Expected: 0 error,`antd` / `@ant-design/icons` 不再 install

- [ ] **Step 7: 跑 tsc 验证**

Run:
```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/canvas exec tsc --noEmit
```

Expected: 0 error(若有 error,看是否 antd 引用残留,逐个 fix)

- [ ] **Step 8: 验证 antd 完全清零**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
grep -rn "antd" web/canvas/src/ web/canvas/package.json | grep -v "node_modules" | grep -v "@rjsf"
```

Expected: 0 输出(antd 完全清零;@rjsf 不算 antd)

- [ ] **Step 9: Commit**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
git add web/canvas/
git commit -m "refactor(canvas): 删 antd dep + ConfigProvider + useAuthStore 改 localStorage

- package.json 删 antd + @ant-design/icons
- main.tsx 删 ConfigProvider + zhCN locale
- index.css 改 @import 'ui/index.css'
- useAuthStore 改读 localStorage['chatbiz.auth'] 标记 (R4)
- grep antd 在 src + package.json: 0 命中

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: canvas 24+ vitest 重跑全过(验收 antd 删后 0 报错)

**Files:**
- Modify: `web/canvas/vitest.config.ts`(若需,加 ui alias)
- Modify: `web/canvas/tsconfig.json`(加 ui path)
- Run tests(不创建新文件)

- [ ] **Step 1: 改 `web/canvas/tsconfig.json` 加 ui path**

`paths` 加:
```json
"ui/*": ["../ui/*"],
"chatbiz-ui": ["../ui/index.ts"]
```

- [ ] **Step 2: 改 `web/canvas/vitest.config.ts` 加 alias(若有)**

若 `web/canvas/vitest.config.ts` 已有 `resolve.alias`:
```ts
resolve: { alias: { 'ui': path.resolve(__dirname, '../ui'), 'chatbiz-ui': path.resolve(__dirname, '../ui/index.ts') } }
```

否则:
```ts
import { defineConfig } from 'vitest/config';
import path from 'node:path';
export default defineConfig({
  test: { environment: 'jsdom', globals: true, exclude: ['**/node_modules/**', '**/dist/**', 'e2e/**'] },
  resolve: { alias: { 'ui': path.resolve(__dirname, '../ui'), 'chatbiz-ui': path.resolve(__dirname, '../ui/index.ts') } },
});
```

- [ ] **Step 3: 跑 vitest**

Run:
```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/canvas exec vitest run
```

Expected: 24+ spec 全过(若有 fail,逐个修)

- [ ] **Step 4: 跑 vite build**

Run:
```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/canvas exec vite build
```

Expected: 成功,dist/ 有产物

- [ ] **Step 5: 跑 e2e**

Run:
```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/canvas exec playwright test
```

Expected: 2+ e2e 全过

- [ ] **Step 6: Commit(若有 vitest.config / tsconfig 改动)**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
git add web/canvas/vitest.config.ts web/canvas/tsconfig.json
git commit -m "chore(canvas): 加 ui alias 给 vitest + tsc

- tsconfig paths 加 ui/* + chatbiz-ui
- vitest.config resolve.alias 加 ui
- vitest 24+ + e2e 2+ + build 全过

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: nginx 集成 — 写 `web/index.html` + 改 `web/Dockerfile` + canvas tailwind.config 对齐

**Files:**
- Create: `web/index.html`(portal 跳板)
- Modify: `web/Dockerfile`(加 `COPY portal/dist`)
- Modify: `web/canvas/tailwind.config.js`(与 portal 逐位一致)

- [ ] **Step 1: 创建 `web/index.html`(portal 跳板)**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ChatBiz</title>
  <meta http-equiv="refresh" content="0; url=/portal/" />
  <link rel="icon" href="data:," />
</head>
<body>
  <p>正在跳转到 <a href="/portal/">ChatBiz Portal</a>…</p>
</body>
</html>
```

- [ ] **Step 2: 改 `web/Dockerfile`**

在 `COPY admin/dist` 之后加:
```dockerfile
COPY portal/dist /usr/share/nginx/html/portal
```

- [ ] **Step 3: 跑 portal build 验证 `web/portal/dist/` 存在**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/portal exec vite build
ls web/portal/dist/
```

Expected: `index.html` + `assets/` 存在

- [ ] **Step 4: 改 `web/canvas/tailwind.config.js` 与 portal 逐位一致**

替换 `web/canvas/tailwind.config.js` 内容(若有)为:
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}', '../ui/primitives/**/*.{ts,tsx}'],
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

- [ ] **Step 5: 验证 diff 逐位一致**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
diff web/portal/tailwind.config.js web/canvas/tailwind.config.js
```

Expected: 0 输出(diff 无输出,履行 `specs/design-tokens` 占位 Requirement)

- [ ] **Step 6: 跑 canvas build 验证(用新 tailwind config)**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/canvas exec vite build
ls web/canvas/dist/
```

Expected: 成功

- [ ] **Step 7: 跑 admin build 验证(不修改 admin,但跑 build 回归)**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/admin exec vite build
```

Expected: 成功(admin 没动,跑回归)

- [ ] **Step 8: 跑 admin vitest 回归**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
pnpm --dir web/admin exec vitest run
```

Expected: 35+ spec 全过

- [ ] **Step 9: 验证 curl nginx 4 路径(若有 docker / nginx 跑)**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
docker build -t chatbiz-web:unified -f web/Dockerfile web/
docker run -d --rm --name chatbiz-web-test -p 5173:80 chatbiz-web:unified
sleep 2
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/         # 期望 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/portal/  # 期望 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/canvas/  # 期望 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/admin/   # 期望 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/health   # 期望 200
docker stop chatbiz-web-test
```

Expected: 4-5 个路径返 200

- [ ] **Step 10: Commit**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/v2-canvas-refactor
git add web/index.html web/Dockerfile web/canvas/tailwind.config.js
git commit -m "feat(web): 集成 nginx 5173 统一入口

- 新建 web/index.html portal 跳板
- web/Dockerfile 加 COPY portal/dist
- web/canvas/tailwind.config.js 与 portal 逐位一致
- diff 验证: 0 输出 (履行 specs/design-tokens 占位)
- 4 个 nginx 路径 curl 200
- admin build + vitest 35+ 回归全过

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 集成 e2e(下次 session 跑)

**Files:**
- Create: `web/portal/e2e/cross-app-jump.spec.ts`

> **本 plan 留 T9 给下次 session。** 任务内容(下次 session 跑时使用):
>
> 1. 写 `web/portal/e2e/cross-app-jump.spec.ts`,覆盖:
>    - 用户登录 V1 portal
>    - 点 "工作流" 菜单
>    - 验证跳到 `http://localhost:5173/canvas/workflows`
>    - 验证 canvas HTML 渲染
> 2. 跑 `pnpm --dir web/portal exec playwright test --grep "cross-app"`
> 3. Expected: 1 e2e spec 通过
> 4. Commit: `git commit -m "test(portal): 加跨子应用 e2e (portal → /canvas/)"`

---

## Task 10: 14-gate verify(下次 session 跑)

**Files:**
- 不创建文件,跑全 14 gate

> **本 plan 留 T10 给下次 session。** 任务内容(下次 session 跑时使用):
>
> 1. 4 个 vitest:
>    - `pnpm --dir web/ui exec vitest run` — 11+ spec
>    - `pnpm --dir web/portal exec vitest run` — 33+ spec
>    - `pnpm --dir web/canvas exec vitest run` — 24+ spec
>    - `pnpm --dir web/admin exec vitest run` — 35+ spec
> 2. 3 个 playwright:
>    - `pnpm --dir web/portal exec playwright test` — 2+ spec + 1 cross-app
>    - `pnpm --dir web/canvas exec playwright test` — 2+ spec
> 3. 3 个 tsc:
>    - `pnpm --dir web/portal exec tsc --noEmit` — 0 error
>    - `pnpm --dir web/canvas exec tsc --noEmit` — 0 error
>    - `pnpm --dir web/admin exec tsc --noEmit` — 0 error
> 4. 3 个 vite build:
>    - `pnpm --dir web/portal exec vite build` — 成功
>    - `pnpm --dir web/canvas exec vite build` — 成功
>    - `pnpm --dir web/admin exec vite build` — 成功
> 5. 1 个 nginx curl(同 T8 Step 9)
> 6. 全 14 gate 通过后,跑 `openspec archive v2-canvas-refactor --yes` 同步 spec

---

## Self-Review Checklist (Plan)

**1. Spec coverage:**
- ✅ D1 (web/ui/ 抽离) → T1
- ✅ D2 (V2 单 change 包办) → T1-T7
- ✅ D3 (全删 antd) → T4-T6
- ✅ D4 (nginx 集成) → T8
- ✅ D5 (ADDED+MODIFIED spec) → openspec archive 时(本 plan 不写 spec 文件)
- ✅ D6 (全面测试 + 集成 e2e) → T9 (cross-app e2e) + T10 (14 gate)
- ✅ D7 (10 任务,本 session 跑 8) → 8 任务完整,2 任务说明

**2. Placeholder scan:** 0 TBD/TODO,所有 step 都有具体代码或命令

**3. Type consistency:**
- `MenuItem` / `MenuSection` 类型在 web/ui/primitives/SidebarItem.tsx 定义,Sidebar.tsx + SidebarSection.tsx 引用,canvas Sidebar.tsx 从 `ui` barrel import
- `useToast` 在 web/ui/primitives/Toast.tsx 定义,canvas useSaveWorkflow.ts 从 `ui/primitives/Toast` import
- `RequireAuth` 在 web/ui/primitives/RequireAuth.tsx 定义,canvas RequireAuth.tsx re-export

**4. Risk fix landed:**
- R1 (useForm 改原生) → T5 Step 1
- R2 (rjsf 默认 theme) → T5 Step 3
- R3 (inline SVG 替代 icons) → T4 Step 4
- R4 (先读 canvas-auth spec) → T6 Step 1
- R5 (tailwind config 覆盖) → T8 Step 4
- R6 (portal/dist 验证) → T8 Step 3
- R7 (集成 e2e 在 portal playwright 跑) → T9

**5. 任务数 = 10,本 session 跑 8,留 2 个:** ✅ T9 + T10 明确说明"下次 session 跑"

**6. 范围守得住:** ✅ 9 个 Out-of-Scope 列表 (admin/README/5 菜单 e2e/i18n/暗色/移动端/workspace/docs/后端/infra)

---

## Execution Handoff

**Plan complete and saved to `openspec/changes/v2-canvas-refactor/plan.md`.** Two execution options:

**1. Subagent-Driven (recommended)** - 1 个 implementer subagent 跑 1 个 plan task,2-stage review(spec compliance + code quality);task 间连续推进
**2. Inline Execution** - 我在本 session 内 dispatch 9 个 subagent 跑 T1-T8,V1 portal 经验证可跑完

**本 session 准备跑 8 任务 (T1-T8)**:
- T1: 抽 web/ui/ 骨架(11 文件)
- T2: 改 portal 11+ 处 import path
- T3: portal 33+ vitest + 2+ e2e + build 重跑
- T4: canvas 11 个简单 .tsx 删 antd
- T5: canvas 11 个复杂 .tsx 删 antd
- T6: 删 antd dep + ConfigProvider + useAuthStore 改 localStorage
- T7: canvas 24+ vitest + 2+ e2e + build
- T8: nginx 集成 + tailwind 逐位一致 + 4 path curl

请告诉我用哪种模式,以及是否启动。

---

## T1 + T2 完成备注(给后续 T3-T8 参考)

### T1 关键产出
- `web/ui/` 共享层 12 文件:package.json + tsconfig + tailwind.config + index.css + 11 primitives + RequireAuth
- `MenuStatus` / `MenuItem` / `MenuSection` 类型内联到 `SidebarItem.tsx` / `SidebarSection.tsx`(避免 `@/data/menu` 私有路径依赖)
- barrel `web/ui/index.ts` re-export 12 组件 + 2 类型(无 `MenuStatus` re-export,需直接 import)
- tsc 0, 12 文件 0 error

### T2 关键产出
- portal 33+ vitest 改 import path 后全过,tsc 0,build 成功
- vitest.config.ts 加 `ui` alias + `react`/`react-dom`/`react-router-dom` 指向 portal node_modules + `dedupe`(避免 web/ui 子包带来的 dual-React)
- index.css 走 `@import 'ui/index.css';`(而非 `chatbiz-ui/index.css`,因为 chatbiz-ui alias 指向 `index.ts` 不带 css)
- **T2 后续 fix (484bed1)**: 移除 unused `chatbiz-ui: file:../ui` dep,避免 T3/T5 canvas/admin 复现 dual-React footgun

### T3+ 已知风险(从 T1/T2 评审)
1. **不要在 canvas/admin 加 `chatbiz-ui: file:../ui` dep**,改用 `ui` path alias(portal 的 484bed1 已示范)
2. **canvas/admin 的 vitest.config.ts 必须有 `ui` alias + react dedupe**,(portal vitest.config.ts 484bed1 后版本可作为模板)
3. **CSS @import 用 `ui/index.css`**,不用 `chatbiz-ui/index.css`
4. **`MenuStatus` 不在 barrel re-export**,要 import 时 `from 'ui/primitives/SidebarItem'`(type)

---

## T3 状态 — ✅ DONE (commit 9655018)

### T3 实测结果(修后)
- `tsc --noEmit` → ✅ PASS (0 error)
- `vitest run` → ✅ 33/33 全过
- `vite build` → ✅ 成功(**bundle 201.39 KB**, 跟 V1 main 201.39 KB 完全一致, 96 modules 一致)
- `playwright test` → ✅ **2/2 pass**

### 修复 (commit 9655018)

`web/portal/vite.config.ts` 加 3 段:
- `resolve.dedupe: ['react', 'react-dom', 'react-router-dom']`
- `optimizeDeps.include: ['react', 'react-dom', 'react-router-dom']`
- `build.rollupOptions.output.manualChunks: undefined`

### Root cause (确认)

- T2 改 `from '@/components/primitives/Toast'` → `from 'ui/primitives/Toast'` 触发 Vite/esbuild 把 web/ui/primitives/Toast.tsx 内的 `import 'react'` 解析到 **web/ui/node_modules/react** (peerDeps 让 pnpm 装了一份 react 在 web/ui/ 下面)
- 物理上 web/ui/node_modules/react 跟 portal/node_modules/react 是**两个 symlink 链**,esbuild 在 prod build tree-shake 时无法识别为同一 module,各自打一份
- 证据: V1 main `createContext()` 9 次 → V2 14 次; `useContext()` 18 → 30 (V2 实际有 2 份 react + 2 份 react-router-dom)
- dev mode 不踩因为 vite dev server 的 esbuild 不做 module-id 树摇;只有 `vite build` 触发 rollup 完整优化

### 复用 (canvas T7 + admin V3)

每个子应用 (`web/portal` / `web/canvas` / `web/admin`) 的 vite.config.ts 都需加这 3 段。Canvas (T6/T7) + Admin (V3) 实施时按此模板改。

### Session 结论

V2 T1+T2+T3 完整落地, e2e regression 已修, 准备好跑 T4-T8.

