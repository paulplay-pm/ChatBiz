import { Suspense, lazy } from "react";
import {
  createBrowserRouter,
  Navigate,
  type RouteObject,
} from "react-router-dom";
import { AppShell } from "@/components/AppShell";
import { MENU_ITEMS } from "@/config/menuItems";

const PlaceholderView = lazy(() =>
  import("@/views/PlaceholderView").then((m) => ({ default: m.PlaceholderView })),
);

// V3: 6 个真实 view(lazy import)
const UsersPage = lazy(() =>
  import("@/views/UsersPage").then((m) => ({ default: m.UsersPage })),
);
const UserAuditPage = lazy(() =>
  import("@/views/UserAuditPage").then((m) => ({ default: m.UserAuditPage })),
);
const RolesPage = lazy(() =>
  import("@/views/RolesPage").then((m) => ({ default: m.RolesPage })),
);
const DepartmentsPage = lazy(() =>
  import("@/views/DepartmentsPage").then((m) => ({ default: m.DepartmentsPage })),
);
const PermissionsPage = lazy(() =>
  import("@/views/PermissionsPage").then((m) => ({ default: m.PermissionsPage })),
);
const DataPermissionsPage = lazy(() =>
  import("@/views/DataPermissionsPage").then((m) => ({ default: m.DataPermissionsPage })),
);

function PlaceholderFallback(): JSX.Element {
  return (
    <div className="max-w-md mx-auto mt-24 text-center text-sm text-ink-400">
      加载中...
    </div>
  );
}

// V3: 6 个真路由(portal 系统管理菜单跳过来)
// 注册顺序在 placeholderRoutes 之前以确保精确匹配优先
const realRoutes: RouteObject[] = [
  {
    path: "/users",
    element: (
      <Suspense fallback={<PlaceholderFallback />}>
        <UsersPage />
      </Suspense>
    ),
  },
  {
    path: "/users/audit",
    element: (
      <Suspense fallback={<PlaceholderFallback />}>
        <UserAuditPage />
      </Suspense>
    ),
  },
  {
    path: "/roles",
    element: (
      <Suspense fallback={<PlaceholderFallback />}>
        <RolesPage />
      </Suspense>
    ),
  },
  {
    path: "/departments",
    element: (
      <Suspense fallback={<PlaceholderFallback />}>
        <DepartmentsPage />
      </Suspense>
    ),
  },
  {
    path: "/permissions",
    element: (
      <Suspense fallback={<PlaceholderFallback />}>
        <PermissionsPage />
      </Suspense>
    ),
  },
  {
    path: "/data-permissions",
    element: (
      <Suspense fallback={<PlaceholderFallback />}>
        <DataPermissionsPage />
      </Suspense>
    ),
  },
];

const placeholderRoutes: RouteObject[] = MENU_ITEMS.map((item) => ({
  path: item.href,
  element: (
    <Suspense fallback={<PlaceholderFallback />}>
      <PlaceholderView menuItemName={item.name} changeName={item.changeName} />
    </Suspense>
  ),
}));

/**
 * 路由表 — spec `route-skeleton` § Requirement: 14 routes registered。
 * - `/` redirect → /workflow
 * - V3 新增 6 个真实路由(`/users`、`/users/audit`、`/roles`、
 *   `/departments`、`/permissions`、`/data-permissions`),
 *   portal 系统管理菜单跳过来
 * - 14 个 menu item 路由全部指向 PlaceholderView（lazy import）
 * - `*` 兜底 404，不崩
 *
 * 后续 change 接入：`import { routes } from "@/router"` 然后 push 或 replace 子路由。
 */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/workflow" replace /> },
      ...realRoutes, // 6 真路由放前
      ...placeholderRoutes, // 14 placeholder
      {
        path: "*",
        element: (
          <div className="max-w-md mx-auto mt-24 text-center">
            <h2 className="text-xl font-semibold text-ink-800 mb-2">404 Not Found</h2>
            <p className="text-sm text-ink-500">该路径未注册路由</p>
          </div>
        ),
      },
    ],
  },
];

export const router = createBrowserRouter(routes, {
  basename: import.meta.env.VITE_APP_BASE?.replace(/\/$/, "") || undefined,
});
