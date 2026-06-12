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

function PlaceholderFallback(): JSX.Element {
  return (
    <div className="max-w-md mx-auto mt-24 text-center text-sm text-ink-400">
      加载中...
    </div>
  );
}

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
      ...placeholderRoutes,
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

export const router = createBrowserRouter(routes);
