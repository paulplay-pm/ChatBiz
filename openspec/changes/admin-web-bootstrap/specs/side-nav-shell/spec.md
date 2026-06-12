# side-nav-shell

**Frontend Scope: 含前端**（SideNav 14 个 menu item + AppShell 双栏布局）

**Impact**（被谁消费）：
- 被 `mcp-server-management-ui` task 7.3-7.8 复用（SideNav 激活 "MCP 工具" 菜单项）
- 被 `mcp-server-management-ui` task 7.7 复用（router 注册路由）
- 未来被所有"前端业务 change"复用

## ADDED Requirements

### Requirement: SideNav renders 14 menu items

The `SideNav` component MUST render exactly 14 menu items in this order (matching `docs/prototype.html:235-410`):
1. 工作流 → `/workflow`
2. Agent → `/agent`
3. 知识库 → `/knowledge`
4. 模板广场 → `/templates`
5. 团队共享 → `/team`
6. 插件市场 → `/plugins`
7. 模型管理 → `/models`
8. 通道管理 → `/channels`
9. 凭证管理 → `/credentials`
10. 技能管理 → `/skills`
11. MCP 工具 → `/mcp-tools`
12. 中间件链 → `/middleware`
13. 监控 → `/monitoring`
14. 日志 → `/logs`

Each item MUST show a FontAwesome 6 Solid icon + Chinese label. The active item MUST have a highlighted background (`bg-brand-50 text-brand-600` per prototype.html:243-247).

#### Scenario: All 14 items render
- **WHEN** user opens `/`
- **THEN** SideNav shows 14 menu items with icons + labels, in the order above

#### Scenario: Active item highlighted
- **WHEN** user navigates to `/mcp-tools`
- **THEN** the "MCP 工具" menu item has highlighted background, others do not

#### Scenario: Click navigates
- **WHEN** user clicks "知识库" menu item
- **THEN** router pushes to `/knowledge` and the view changes to PlaceholderView for `/knowledge`

### Requirement: AppShell two-column layout

The `AppShell` component MUST render a two-column layout: 256px wide sidebar (SideNav) on the left, flex-1 main area on the right. The layout MUST use Tailwind `flex h-screen` and the sidebar MUST be `w-64 bg-white border-r border-ink-200`. The main area MUST have a header bar (h-14, white background, border-b) and a content area (flex-1, p-6, overflow-y-auto) — matching `docs/prototype.html:201-230`.

#### Scenario: Layout renders correctly
- **WHEN** user opens `/`
- **THEN** the page shows a left sidebar (256px) and a main content area to the right

#### Scenario: Main area is scrollable
- **WHEN** user resizes the window to 800px height and main content overflows
- **THEN** the main area scrolls, the sidebar does not

### Requirement: SideNav is keyboard-navigable

Each menu item MUST be a `<a>` (or `<NavLink>`) element with `href` set, focusable via Tab, and Enter MUST navigate. The active item MUST have `aria-current="page"`.

#### Scenario: Tab focus
- **WHEN** user presses Tab from the URL bar
- **THEN** focus moves through menu items in DOM order

#### Scenario: Enter activates
- **WHEN** user focuses a menu item and presses Enter
- **THEN** router navigates to the item's href

#### Scenario: Active aria
- **WHEN** user is on `/mcp-tools`
- **THEN** the "MCP 工具" link has `aria-current="page"` attribute

### Requirement: SideNav visual matches prototype.html

The SideNav MUST use:
- Width: 256px (`w-64`)
- Background: white (`bg-white`)
- Right border: 1px ink-200 (`border-r border-ink-200`)
- Section title: 11px uppercase ink-400 (`text-[11px] font-semibold text-ink-400 uppercase tracking-wider`)
- Menu item height: 36px (`h-9`)
- Menu item text: 14px ink-700 (`text-sm text-ink-700`)
- Menu item icon: 16px wide (`w-4`)
- Active item: brand-50 background + brand-600 text (`bg-brand-50 text-brand-600`)

#### Scenario: Visual matches
- **WHEN** user opens `/` and compares SideNav to prototype.html screenshot
- **THEN** width / background / fonts / colors / spacing are visually identical
