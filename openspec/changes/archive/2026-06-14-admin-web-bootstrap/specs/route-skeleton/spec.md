# route-skeleton

**Frontend Scope: 含前端**（React Router 6 + 11+1 路由 + 重定向）

**Impact**（被谁消费）：
- 被 `mcp-server-management-ui` task 7.7 复用（添加 `/mcp-tools` 路由 + lazy import）
- 被未来所有"前端业务 change"复用（添加业务路由 + lazy import）
- 被 placeholder-view capability 消费（未匹配路由 → placeholder）

## ADDED Requirements

### Requirement: 14 routes registered

The system MUST register exactly 14 routes (one per SideNav menu item) using `createBrowserRouter` from React Router 6:
- `/` → redirect to `/workflow`
- `/workflow` → PlaceholderView
- `/agent` → PlaceholderView
- `/knowledge` → PlaceholderView
- `/templates` → PlaceholderView
- `/team` → PlaceholderView
- `/plugins` → PlaceholderView
- `/models` → PlaceholderView
- `/channels` → PlaceholderView
- `/credentials` → PlaceholderView
- `/skills` → PlaceholderView
- `/mcp-tools` → PlaceholderView
- `/middleware` → PlaceholderView
- `/monitoring` → PlaceholderView
- `/logs` → PlaceholderView

`/` MUST use `<Navigate to="/workflow" replace />` (or `redirect()` loader).

#### Scenario: Root redirect
- **WHEN** user opens `/`
- **THEN** URL changes to `/workflow` and PlaceholderView for `/workflow` renders

#### Scenario: Direct deep link
- **WHEN** user opens `/mcp-tools` directly
- **THEN** PlaceholderView for `/mcp-tools` renders with SideNav showing "MCP 工具" as active

#### Scenario: Unknown route 404
- **WHEN** user opens `/nonexistent`
- **THEN** the router matches no route and shows a fallback 404 (e.g. plain text "404 Not Found") — NOT crashes

### Requirement: Routes use lazy import

Every PlaceholderView MUST be loaded via `React.lazy()` to enable code splitting. The build output MUST contain separate chunks per route.

#### Scenario: Code splitting works
- **WHEN** developer runs `pnpm build`
- **THEN** `dist/assets/` contains multiple JS chunks, NOT a single bundle

#### Scenario: Lazy loading
- **WHEN** user navigates to `/mcp-tools`
- **THEN** the chunk for `/mcp-tools` is fetched on demand (visible in DevTools Network tab)

### Requirement: Router exports a typed routes config

The router MUST export a typed `routes: RouteObject[]` constant, so future changes can import it and extend (e.g. add `/mcp-tools` lazy child routes from `mcp-server-management-ui`).

#### Scenario: Future extension
- **WHEN** `mcp-server-management-ui` writes `import { routes } from "@/router"` and pushes a new route
- **THEN** TypeScript validates the new RouteObject shape and the route appears in the app
