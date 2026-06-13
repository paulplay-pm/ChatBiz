# v2-canvas-refactor — Design

> **For agentic workers:** 写实施计划时,本 design.md 配合 `tasks.md` + 既有 `openspec/specs/{canvas-shell,design-tokens,tailwind-primitive-library}/spec.md` 一起读。

**Goal:** 把 `web/canvas` 22 处 antd 引用全部换成 tailwind + 共享 `web/ui/` primitives,集成 nginx 5173 统一入口,落地 V1 推迟的"三套子应用共享"目标。

**Architecture:**
- 抽出 `web/ui/` 共享层(11 primitives + tailwind config + index.css),作为 portal/canvas/admin 的单一 source
- 删 `web/canvas` 的 antd + @ant-design/icons + ConfigProvider + zhCN locale
- 把 `web/canvas/tailwind.config.js` 与 portal 逐位对齐(履行 `specs/design-tokens/spec.md` 占位 Requirement)
- 集成 `web/nginx.conf` + `web/Dockerfile` 让 portal 走 `/`,canvas 走 `/canvas/`,admin 走 `/admin/`
- 写 `web/index.html` portal 跳板(预先 `web/nginx.conf` 已配,只缺 dist)

**Tech Stack:** Vite 5 + React 18 + TypeScript 5.4 strict + Tailwind 3.4(沿用 V1)+ React Router 6 + @tanstack/react-query 5 + zustand 4 + @xyflow/react 12 + @rjsf 5(保留,非 antd)

---

## Context

**Background.** V1 portal 已落地 `web/portal/` + 11 个 primitives + design tokens + 30+ 项菜单 + Login/Dashboard/ComingSoon 页面。V1 design.md §"V2/V3 显式不在 V1 范围"明确推迟:
- V2: canvas 删 antd 改 tailwind + 配 `specs/canvas-shell` MODIFIED delta
- V3: admin 删 antd 改 tailwind
- V2 + V3 一起做:`web/nginx.conf` + `web/Dockerfile` 集成 + `web/README.md`

**Current state.**
- `web/canvas/`: 24 处 antd 引用(grep 计数 24),分布在 22 .tsx 文件(`AppLayout` / `ErrorBoundary` / `CreateWorkflowModal` / `DeleteConfirmModal` / `WorkflowCard` / `Sidebar` / `TopBar` / `canvas/*` / `chatflow/*` / `debugger/*` / `pages/*`)+ `main.tsx`(ConfigProvider + zhCN)
- `web/canvas/package.json`: 含 `antd@5.20.0` + `@ant-design/icons@5.4.0` + `@rjsf/*@5.22.0`(保留,非 antd)
- `web/portal/`: V1 已建,11 primitives 在 `web/portal/src/components/primitives/`,`tailwind.config.js` 与 `docs/prototype.html:7-40` 逐位一致
- `web/admin/`: 2026-06-12 `admin-web-bootstrap` 落地 src 骨架;V2 **不动** admin(留给 V3)
- `web/nginx.conf`: 预先写好 portal 在 `/`,canvas 在 `/canvas/`,admin 在 `/admin/`,包含 SPA fallback + cache 规则
- `web/Dockerfile`: 预先写好 `COPY index.html` + `COPY canvas/dist` + `COPY admin/dist` + `COPY nginx.conf`,只缺 `COPY portal/dist`
- `web/index.html`: **未创建**(V1 期间 portal 独立 dev 5174,不需要跳板)
- `openspec/specs/canvas-shell/spec.md`: 7 个 Requirement,硬编码 antd:`notification` / `ConfigProvider` / 4 类 toast color
- `openspec/specs/design-tokens/spec.md`: 含 V2/V3 占位 Requirement"M2/V3 集成时三套 tailwind.config.js 逐位一致"
- `openspec/specs/tailwind-primitive-library/spec.md`: 11 个 V1 已落地的 primitives spec;V2 canvas 复用同一组

**V2 范围**(本 change 唯一范围):
1. 抽 `web/ui/` 共享层
2. 改 portal import path 指向 `web/ui/`
3. canvas 22 .tsx 删 antd 改 tailwind
4. 改 `web/canvas/package.json` 删 antd 依赖
5. canvas 复用 `web/ui/` primitives
6. 集成 `web/nginx.conf` + `web/Dockerfile` + 写 `web/index.html`
7. 集成 e2e: portal 点击 "工作流" 跳 `/canvas/`,返 200

**V2 不做**(留给 V3 或后续):
- admin 改 antd(V3)
- 跨子应用 e2e 覆盖 admin(V3)
- 国际化(V1 N6 已推迟)
- 暗色模式(V1 N7 已推迟)
- 移动端响应式(V1 N8 已推迟)
- 写 `web/README.md` 统一三套子应用说明(V3)
- 集成 e2e 覆盖所有 5 个菜单入口(V3,本次只覆盖"工作流" 1 个)

**Stakeholders.**
- paul(财务运营)— V1 portal 的"工作流"菜单跳转进 canvas
- 前端组 — V2 主要实施者(跟 V1 同一批)
- C-level sponsor — 集成后的统一入口

**Constraints from CLAUDE.md / openspec/config.yaml.**
- CLAUDE.md 强制: 统一前端在 `web/` 下,V2 新建 `web/ui/`
- CLAUDE.md 强制: `VITE_APP_BASE=/<frontend-name>/` — V2 不动 V1 portal 已有 `/portal/`
- CLAUDE.md 强制: worktree 必须放 `.worktrees/`,V2 worktree 名 `v2-canvas-refactor`
- openspec/config.yaml 强制: 简体中文,SHALL/MUST,每 Requirement 配 WHEN/THEN,任务 ≤2h
- openspec/config.yaml 强制: 单元 ≥100% / 接口 100% / 安全全覆盖

---

## Decisions (5 关键点已与 user 锁定)

### D1: Primitive 共享 = 抽到 `web/ui/`

- **选择**: 在 `web/` 下新建 `web/ui/`,放 11 个 primitives + `tailwind.config.js` + `index.css`(glass / status-* / metric-card / node-shadow / pulse 动画)
- **结构**:
  ```
  web/
    ui/                          # 新建
      package.json
      tailwind.config.js         # 单一 source(V1 portal 那份平移)
      index.css                  # glass / status-* / metric-card / node-shadow
      tsconfig.json
      primitives/
        Button.tsx
        Card.tsx
        MetricCard.tsx
        StatusDot.tsx
        Input.tsx
        Form.tsx
        Modal.tsx
        Toast.tsx                # 含 useToast hook + ToastProvider
        Sidebar.tsx
        SidebarItem.tsx
        SidebarSection.tsx
      index.ts                   # barrel export
  portal/src/...                 # import from @ui
  canvas/src/...                 # import from @ui
  admin/src/...                  # import from @ui (V3)
  ```
- **理由**: 单一 source 满足 `specs/design-tokens` 占位 Requirement"diff 无输出";未来 admin 复用零成本
- **已考虑 alternative**:
  - 复制 11 份到各子应用(被弃): diff 维护成本高
  - pnpm workspace 抽到 `web/packages/primitives/`(被弃): V2 overkill

### D2: V2 单 change 包"抽 web/ui/ + canvas 复用",不拆 V0 + V2

- **选择**: V2 包含"创建 web/ui/ + 移动 V1 portal 11 个 primitives + 改 portal import + canvas 复用 web/ui/"
- **理由**: 1 个 change 跑完,不依赖 V0 先存在;portal 改 import path 的 vitest 重跑 = 验证 web/ui/ 抽离正确
- **已考虑 alternative**:
  - 单起 V0 change 抽 web/ui/(被弃): 多一轮往返,V1 portal import 改完才能跑 V2
  - V2 + V3 一起做(被弃): scope 太大,1 session 跑不完

### D3: 全删 antd + @ant-design/icons + ConfigProvider(包含 zhCN locale)

- **选择**: `web/canvas/package.json` 删 `antd@5.20.0` + `@ant-design/icons@5.4.0`;`main.tsx` 删 `ConfigProvider` + `zhCN` import;`@rjsf/*` 保留(非 antd)
- **理由**: V2 spec Requirement "web/canvas MUST NOT 依赖 antd" 才有意义;留 antd dep 未来会被误用
- **已考虑 alternative**:
  - 不删 antd dep(被弃): spec 难于"干净"
  - 只改低难度部分(被弃): spec 不完整

### D4: 集成 nginx 5173,根路径换为 portal

- **选择**: `web/nginx.conf` 已写好 portal 在 `/`,canvas 在 `/canvas/`,admin 在 `/admin/`,V2 **不动 nginx.conf**(已就绪);写 `web/index.html` portal 跳板;`web/Dockerfile` 加 `COPY portal/dist`
- **集成验证**:
  ```bash
  curl http://localhost:5173/         # 200, HTML 含 portal
  curl http://localhost:5173/canvas/  # 200, HTML 含 canvas
  curl http://localhost:5173/admin/   # 200, HTML 含 admin
  ```
- **理由**: `web/nginx.conf` 跟 `web/Dockerfile` 在 V1 cycle 已经预留(V1 集成选项),V2 实际工作量小
- **已考虑 alternative**:
  - V2 不集成,3 套独立 dev(被弃): 与 V1 design.md 推迟目标冲突
  - 根路径不动(被弃): user 明确选 A

### D5: spec 走 ADDED + MODIFIED 混合

- **选择**: V2 写 2 个文件到 `openspec/changes/v2-canvas-refactor/specs/`:
  - **NEW** `canvas-refactor/spec.md`: 2 个 ADDED Requirement
    - R1: `web/canvas` MUST NOT 依赖 antd(@ant-design/icons / ConfigProvider / zhCN 一并清零)
    - R2: `web/canvas` MUST 复用 `web/ui/` primitives(11 个组件 + tailwind config + index.css,逐位一致)
  - **MODIFIED** `canvas-shell/spec.md`: 3 个 delta
    - M1: 顶部栏(原 Requirement "顶部栏 + 侧边栏" 修改,与 V1 portal 一致 design language)
    - M2: 错误边界(原 Requirement "错误边界 + 全局 toast" 修改,用 `useToast` 替代 antd `notification`,颜色与 `specs/tailwind-primitive-library` 一致:security=red-500 / user=yellow-500 / runtime=brand-500)
    - M3: Zustand store(原 Requirement "Zustand 全局 store" 修改,JWT 改成走 `localStorage['chatbiz.auth']` 标记,跟 V1 portal + canvas-auth 契约一致;其余 useUIStore / useCanvasEditStore 不变)
- **archive 时**: openspec CLI 把 ADDED 同步到 `openspec/specs/canvas-refactor/spec.md`(新建),把 MODIFIED 同步到 `openspec/specs/canvas-shell/spec.md`(覆盖 3 个原 Requirement)
- **理由**: openspec 自带 ADDED + MODIFIED schema,混合最自然;原 7 个 Requirement 中 4 个不动,3 个改 MODIFIED
- **已考虑 alternative**:
  - 只 ADDED 不 MODIFIED(被弃): 原 spec 不反映 V2 变动
  - 全 MODIFIED 不新增 spec(被弃): 7 个原 Requirement 全部加 MODIFIED 标记,diff 复杂

### D6: 测试 gate = 全面测试 + 集成 e2e

- **选择**: V2 完成时跑 14 个 gate:
  - 4 个 vitest:`web/ui/` + `web/portal/`(33+)+ `web/canvas/`(24+)+ `web/admin/`(35+,V2 不改但回归)
  - 3 个 playwright:`web/portal/`(2+)+ `web/canvas/`(2+)+ 集成 e2e(1 个,portal → canvas 跳转)
  - 3 个 tsc:`web/portal/` + `web/canvas/` + `web/admin/`
  - 3 个 vite build:`web/portal/` + `web/canvas/` + `web/admin/`
  - 1 个 nginx curl: `http://localhost:5173/{,canvas,admin,health}`
- **理由**: 与 V1 portal `33 vitest + 2 playwright` 基准对等;canvas 改 22 .tsx + 删 antd,回归必须
- **已考虑 alternative**:
  - 只重 canvas + web/ui/,portal V1 同步跑(被弃): user 选 A
  - 4 个新集成 e2e(被弃): 过重,V2 只覆盖"工作流" 1 个跨子应用跳转

### D7: 任务粒度 = 10 个 plan 任务(细粒度),本 session 跑 8 个,留 2 个下次

- **选择**: V2 拆 10 个 plan 任务,本 session 跑 T1-T8(8 个),T9(集成 e2e)+ T10(verify)留下次 session
- **理由**: V1 portal 跑过 6 任务本 session,V2 估计 8-10 任务;细粒度 bug 范围小;剩 2 任务下次 session 跑完即可 archive
- **10 任务清单**:
  - T1: 抽 `web/ui/` 骨架(11 primitives + tailwind config + index.css + package.json + tsconfig + index.ts)
  - T2: 改 `web/portal/src/**` 8+ 处 import path(primitives / tailwind config / index.css)
  - T3: `web/portal` 33+ vitest 重跑全过(验收 web/ui/ 抽离正确)
  - T4: canvas 11 个简单 .tsx 删 antd 改 tailwind(`AppLayout` / `ErrorBoundary` / `CreateWorkflowModal` / `DeleteConfirmModal` / `WorkflowCard` / `Sidebar` / `TopBar` / `pages/LoginPage` / `pages/NotFoundPage` / `pages/SettingsPage` / `pages/ChatflowPage`)
  - T5: canvas 11 个复杂 .tsx 删 antd 改 tailwind(`canvas/NodePanel` / `canvas/ConfigPanel` / `canvas/EdgeConditionMenu` / `canvas/NodeSearchModal` / `chatflow/ApprovalInlineCard` / `debugger/NodeEventTimeline` / `debugger/RetryCancelButtons` / `pages/CanvasPage` / `pages/RunDebuggerPage` / `pages/WorkflowListPage` / `hooks/useSaveWorkflow`)
  - T6: canvas `package.json` 删 antd + `@ant-design/icons`;`main.tsx` 删 `ConfigProvider` + `zhCN` import
  - T7: canvas 24+ vitest 重跑全过(验收删 antd 后 0 报错)
  - T8: 写 `web/index.html` portal 跳板 + 改 `web/Dockerfile` 加 `COPY portal/dist` + 改 `web/canvas/tailwind.config.js` 与 portal 逐位一致
  - **T9 (下次)**: 集成 e2e — `web/portal/e2e/cross-app-jump.spec.ts`,portal 登录后点 "工作流" 跳到 `http://localhost:5173/canvas/`,验证 200 + 含 canvas HTML
  - **T10 (下次)**: verify — 14 gate 全过(`4 vitest + 3 playwright + 3 tsc + 3 vite build + 1 curl`)
- **已考虑 alternative**:
  - 6 任务粗粒度(被弃): bug 范围大,web/ui/ 抽 + portal 改 + canvas 22 tsx 一起动难定位
  - 4 任务超粗(被弃): user 选 B

---

## Goals / Non-Goals

**Goals:**

- **G1**: `web/ui/` 共享层落地,11 primitives + tailwind config + index.css + package.json,`web/portal` 33+ vitest 改 import path 后全过
- **G2**: `web/canvas` 24 处 antd 引用清零,`package.json` 不含 `antd` / `@ant-design/icons`,`@rjsf/*` 保留
- **G3**: `web/canvas` 复用 `web/ui/` primitives(顶部栏 / 错误边界 / 卡片 / 模态 / toast 全部走 primitives)
- **G4**: `web/canvas/tailwind.config.js` 与 `web/portal/tailwind.config.js` 逐位一致,履行 `specs/design-tokens` 占位 Requirement
- **G5**: 集成 `web/nginx.conf`(不改)+ `web/Dockerfile`(加 1 行)+ 写 `web/index.html` portal 跳板
- **G6**: 集成 e2e 覆盖 portal 跳 canvas 1 个关键路径
- **G7**: V2 archive 后 `openspec/specs/canvas-refactor/spec.md` 新建 + `openspec/specs/canvas-shell/spec.md` 3 个 MODIFIED delta 同步
- **G8**: 14 个 build gate 全过(4 vitest + 3 playwright + 3 tsc + 3 vite build + 1 curl)
- **G9**: V2 期间不动 admin(V3 接管);不动 docs/architecture.md / docs/prd.md / design doc;不动后端 services
- **G10**: V2 期间 V1 V1 33+ vitest 仍跑通(改 import path 后)

**Non-Goals:**

- **N1**: 任何后端 API 实现 — V2 仅前端
- **N2**: admin 任何修改 — V3 独立 change 接管
- **N3**: 写 `web/README.md` 统一三套子应用说明 — V3 一起做
- **N4**: 集成 test 覆盖 admin — V3 一起做
- **N5**: 集成 e2e 覆盖 5 个菜单入口 — V2 只覆盖"工作流" 1 个
- **N6**: 国际化、暗色模式、移动端 — 沿用 V1 N6/N7/N8 推迟
- **N7**: pnpm workspace 抽 `@chatbiz/primitives` — V2 用本地 `web/ui/`,V3+ 视情况
- **N8**: 改 docs/architecture.md / docs/prd.md — V2 是实施 change,不改设计文档
- **N9**: 改 12 个 eng-review locked 决策 — V2 履行,不重讨论
- **N10**: 真实 OAuth / SSO — 沿用 V1 dev fallback

---

## Architecture(详细)

### 文件结构(V2 完成时)

```
web/
  ui/                                  # 新建
    package.json                       # name: chatbiz-ui, main: src/index.ts
    tailwind.config.js                 # 单一 source
    tsconfig.json                      # strict + noUncheckedIndexedAccess
    index.css                          # @tailwind + glass + status-* + metric-card + node-shadow + pulse
    primitives/
      Button.tsx                       # 从 web/portal 平移
      Card.tsx
      MetricCard.tsx
      StatusDot.tsx
      Input.tsx
      Form.tsx
      Modal.tsx
      Toast.tsx
      Sidebar.tsx
      SidebarItem.tsx
      SidebarSection.tsx
    index.ts                           # barrel export

  portal/
    package.json                       # 改: 加 "chatbiz-ui": "file:../ui"
    tsconfig.json                      # 改: paths "ui/*": ["../ui/*"]
    tailwind.config.js                 # 改: content 加 "../ui/**/*.{ts,tsx}", preset 指向 web/ui/tailwind.config.js
    src/
      index.css                        # 改: import '../ui/index.css'
      main.tsx                         # 改: 0 行(本来就不引 antd)
      App.tsx                          # 不动
      components/
        AppLayout.tsx                  # 改: import from 'ui/primitives/Sidebar'
        RequireAuth.tsx                # 改: import from 'ui/primitives/RequireAuth'(待定,见 T1)
        primitives/                    # 删除整个目录
      pages/                           # 改: import from 'ui/primitives/Button'
      data/menu.ts                     # 不动
      router/index.tsx                 # 不动
    e2e/                               # 改: cross-app-jump.spec.ts(T9 加)
    tests/                             # 33+ vitest,改 import path

  canvas/
    package.json                       # 改: 删 antd + @ant-design/icons, 加 chatbiz-ui
    tsconfig.json                      # 改: paths "ui/*": ["../ui/*"]
    tailwind.config.js                 # 改: 与 web/portal/tailwind.config.js 逐位一致
    vite.config.ts                     # 不动
    src/
      index.css                        # 改: import '../ui/index.css'
      main.tsx                         # 改: 删 ConfigProvider + zhCN
      App.tsx                          # 改: 0 行
      components/                      # 22 .tsx 改 antd 引用
        AppLayout.tsx
        ErrorBoundary.tsx
        Sidebar.tsx
        TopBar.tsx
        CreateWorkflowModal.tsx
        DeleteConfirmModal.tsx
        WorkflowCard.tsx
        RequireAuth.tsx
        canvas/
          NodePanel.tsx
          ConfigPanel.tsx
          EdgeConditionMenu.tsx
          NodeSearchModal.tsx
        chatflow/
          ApprovalInlineCard.tsx
        debugger/
          NodeEventTimeline.tsx
          RetryCancelButtons.tsx
      pages/                           # 7 .tsx 改 antd 引用
        LoginPage.tsx
        NotFoundPage.tsx
        SettingsPage.tsx
        CanvasPage.tsx
        RunDebuggerPage.tsx
        WorkflowListPage.tsx
        ChatflowPage.tsx
      hooks/
        useSaveWorkflow.ts             # 改 antd 引用

  admin/                               # V2 不动,保留 V1 bootstrap src 骨架
    src/                               # 11+ 占位菜单 + SideNav + AppShell + PlaceholderView
  index.html                           # 新建: portal 跳板 + redirect
  Dockerfile                           # 改: 加 COPY portal/dist
  nginx.conf                           # 不动(已就绪)
  README.md                            # 不动(V3 一起写)
```

### Spec deltas(`openspec/changes/v2-canvas-refactor/specs/`)

#### File 1: `canvas-refactor/spec.md` (NEW)

```yaml
# canvas-refactor Specification
## Purpose
TBD - created by archiving change v2-canvas-refactor.
## Requirements
### Requirement: web/canvas MUST NOT 依赖 antd
... (R1: 全删 antd + @ant-design/icons + ConfigProvider + zhCN;@rjsf 保留)
### Requirement: web/canvas MUST 复用 web/ui/ primitives
... (R2: 11 个 primitive 走 ui 包 import;tailwind config 逐位一致)
```

#### File 2: `canvas-shell/spec.md` (MODIFIED — 3 deltas)

```yaml
### Requirement: 顶部栏 + 侧边栏 (MODIFIED)
原 V1: 硬编码 antd `<Layout>` / `<Menu>` / `<Icon>`。
V2 改: 改用 `ui/primitives/Sidebar` + `ui/primitives/Button`,与 V1 portal 顶部栏 design language 一致。
### Requirement: 错误边界 + 全局 toast (MODIFIED)
原 V1: 用 antd `notification`,4 类 toast color 硬编码。
V2 改: 用 `ui/primitives/Toast` + `useToast` hook,3 类 toast color 与 `specs/tailwind-primitive-library` 一致(security=red-500 / user=yellow-500 / runtime=brand-500)。
### Requirement: Zustand 全局 store (MODIFIED)
原 V1: `useAuthStore` 存 JWT 到内存,`localStorage` 持久化 UI。
V2 改: `useAuthStore` 改读 `localStorage['chatbiz.auth']` 标记(沿用 V1 portal + canvas-auth dev fallback 契约);JWT 不在 client 存;其余 useUIStore / useCanvasEditStore 不变。
```

### Tasks(10 任务,见 D7)

每个 task 配 vitest + 1 commit;**T1-T3** 是 web/ui/ 抽 + portal 改 import;**T4-T7** 是 canvas 删 antd;**T8** 是 nginx 集成;**T9-T10** 是 e2e + verify(下次 session)。

### 数据流

- `web/portal` 用户登录 → 写 `localStorage['chatbiz.auth']`(username + loginAt)
- 点 "工作流" 菜单 → V1 portal router 跳 `<a href="/canvas/">` 标签(V1 已实现)
- nginx `location /canvas/` 返 `web/canvas/dist/index.html`
- canvas 启动 → RequireAuth 读 `localStorage['chatbiz.auth']` → 已登录 → 渲染 AppLayout → 路由 `/workflows`
- 错误边界 → 走 `ui/primitives/Toast` 红色 toast + 跳 login
- 顶部栏用户头像 → 读 `localStorage['chatbiz.auth']` 拿 username

### 错误处理

- web/ui/ 抽离后 portal 33+ vitest 失败 → T3 立即发现,回滚到 V1 portal(只动 import path,易回滚)
- canvas 22 .tsx 删 antd 编译失败 → T6/T7 期间持续修,逐 tsx 解决
- nginx 集成 curl 404 → T8 期间修 `web/index.html` / `web/Dockerfile` COPY
- 集成 e2e 失败 → T9,可能 portal 跳转路径不匹配 /canvas/

### 测试

- 单元(vitest): web/ui/ + web/portal 33+ + web/canvas 24+ + web/admin 35+(回归)
- 端到端(playwright): web/portal 2+ + web/canvas 2+ + 集成 e2e 1(portal → /canvas/)
- 静态(tsc): web/portal + web/canvas + web/admin
- 构建(vite build): web/portal + web/canvas + web/admin
- 集成(curl): 4 个 nginx 路径

---

## Risk Surfaces

- **R1**: canvas 22 .tsx 中有 7+ 处 `useForm` / `Form.useForm` 等 antd 专属 API,删 antd 后需重写为 react-hook-form / 原生 form(选择原生,跟 V1 portal 一致)
- **R2**: ConfigPanel 用 `@rjsf/core` 是非 antd,但可能配套 `antd` theme provider;删 antd 后 rjsf 主题失效 → 需替换为 rjsf 默认主题或自定义 tailwind
- **R3**: TopBar 可能用了 `@ant-design/icons`(search / bell / user 图标)→ 需替换为 inline SVG / lucide-react / heroicons(三选一,V1 portal 没用 icons,V2 选 inline SVG)
- **R4**: Zustand `useAuthStore` 改成 `localStorage['chatbiz.auth']` 标记,跟 V1 portal + canvas-auth 契约一致;若 canvas-auth spec 有冲突,以 canvas-auth 为准(CLAUDE.md source-of-truth 顺序)
- **R5**: `web/canvas/tailwind.config.js` 原本可能存在但内容跟 portal 不一致 → T8 覆盖为 portal 逐位一致版
- **R6**: `web/Dockerfile` 加 `COPY portal/dist` 可能在 V1 portal 部署时缺 `portal/dist/` 目录 → T8 验证 `vite build` 跑通
- **R7**: 集成 e2e 在 web/portal `playwright.config.ts` 跑还是新建 `web/integration/playwright.config.ts`?选 portal(V1 portal playwright 配置已就绪)

---

## Out of Scope(明确不做)

1. admin 改 antd(V3)
2. `web/README.md` 统一三套子应用说明(V3)
3. 集成 e2e 覆盖 admin / 5 个菜单入口(V3+)
4. 国际化、暗色模式、移动端响应式
5. pnpm workspace 抽 `@chatbiz/primitives` npm 包
6. 改 docs/architecture.md / docs/prd.md / design doc
7. 改 12 个 eng-review locked 决策
8. 改后端 services 或 infra 配置(除 web/Dockerfile 一行)
9. 改 web/nginx.conf(已就绪)
10. 改 `services/audit-and-isolation/app/pii/{rules,detector,redactor,reverser}.py`(eng-review locked)

---

## Reference

- V1 design: `openspec/changes/archive/2026-06-13-web-portal-shell/design.md`(V2/V3 推迟范围)
- V1 portal primitives: `web/portal/src/components/primitives/*`(11 文件,平移到 web/ui/)
- V1 portal vitest: `web/portal/tests/**`(33 spec)
- V1 spec baseline: `openspec/specs/{portal-shell,design-tokens,tailwind-primitive-library}/spec.md`
- V2 spec baseline: `openspec/specs/canvas-shell/spec.md`(7 Requirement,3 个改 MODIFIED)
- 12 eng-review locked 决策: CLAUDE.md "已锁定的工程决策"
- 端口分配: CLAUDE.md "端口分配表"
- 前端目录约定: CLAUDE.md "前端目录与端口约定"
- worktree 约定: CLAUDE.md "worktree 目录"
