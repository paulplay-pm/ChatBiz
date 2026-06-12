import { NavLink } from "react-router-dom";
import clsx from "clsx";
import { MENU_ITEMS } from "@/config/menuItems";

/**
 * 左侧导航 — 14 个 menu item。spec `side-nav-shell` § Requirement: SideNav renders 14 menu items。
 * 视觉对齐 `docs/prototype.html:235-410`。
 */
export function SideNav(): JSX.Element {
  return (
    <nav
      aria-label="主导航"
      className="w-64 bg-white border-r border-ink-200 flex flex-col h-full shrink-0"
    >
      <div className="px-4 py-4 border-b border-ink-200 flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center">
          <i className="fas fa-robot text-white text-sm" aria-hidden="true" />
        </div>
        <span className="font-semibold text-sm text-ink-800">ChatBiz Admin</span>
      </div>
      <div className="px-4 py-2 text-[11px] font-semibold text-ink-400 uppercase tracking-wider">
        工作区
      </div>
      <ul className="flex-1 overflow-y-auto px-2 pb-4 space-y-0.5">
        {MENU_ITEMS.map((item) => (
          <li key={item.href}>
            <NavLink
              to={item.href}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-2 px-3 h-9 rounded-lg text-sm transition-colors",
                  isActive
                    ? "bg-brand-50 text-brand-600 font-medium"
                    : "text-ink-700 hover:bg-ink-100",
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
