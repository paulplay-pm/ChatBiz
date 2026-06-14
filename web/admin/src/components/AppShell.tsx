import { Outlet } from "react-router-dom";
import { SideNav } from "./SideNav";
import { HealthIndicator } from "./HealthIndicator";

/**
 * AppShell — 双栏布局，spec `side-nav-shell` § Requirement: AppShell two-column layout。
 * - 左 256px SideNav
 * - 右 main 区：h-14 header bar + flex-1 content
 */
export function AppShell(): JSX.Element {
  return (
    <div className="flex h-screen">
      <SideNav />
      <main className="flex-1 flex flex-col h-full min-w-0">
        <header className="h-14 bg-white border-b border-ink-200 flex items-center px-5 gap-4 shrink-0">
          <h1 className="font-semibold text-sm text-ink-800">系统管理</h1>
          <div className="ml-auto flex items-center gap-3">
            <HealthIndicator />
            <div
              className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white text-sm font-bold"
              aria-label="当前用户：张"
            >
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
