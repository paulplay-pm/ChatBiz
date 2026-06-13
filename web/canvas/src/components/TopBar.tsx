import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/useAuthStore';
import { useUIStore } from '@/store/useUIStore';

const IconMenu = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="3" y1="6" x2="21" y2="6" />
    <line x1="3" y1="12" x2="21" y2="12" />
    <line x1="3" y1="18" x2="21" y2="18" />
  </svg>
);
const IconBell = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M6 8a6 6 0 0112 0c0 7 3 9 3 9H3s3-2 3-9z" />
    <path d="M10 21a2 2 0 004 0" />
  </svg>
);
const IconUser = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21v-1a8 8 0 0116 0v1" />
  </svg>
);
const IconLogout = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
    <polyline points="16 17 21 12 16 7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);

export function TopBar() {
  const navigate = useNavigate();
  const { user, clear } = useAuthStore();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  const logout = () => {
    clear();
    navigate('/login');
  };

  const displayName = user?.name ?? 'guest';
  const initial = user?.name?.[0]?.toUpperCase() ?? 'G';

  return (
    <header className="glass h-14 flex items-center justify-between px-4 flex-shrink-0 border-b border-ink-200">
      <div className="flex items-center gap-3">
        <button
          onClick={toggleSidebar}
          className="rounded-lg p-1.5 hover:bg-ink-100 text-ink-700"
          aria-label="toggle sidebar"
          title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
        >
          <IconMenu />
        </button>
        <div className="text-lg font-semibold text-ink-900">ChatBiz</div>
      </div>
      <div className="flex items-center gap-3">
        <button
          className="rounded-lg p-1.5 hover:bg-ink-100 text-ink-700 relative"
          aria-label="notifications"
          title="通知"
        >
          <IconBell />
        </button>
        <div className="relative group">
          <button
            className="flex items-center gap-2 rounded-lg p-1.5 hover:bg-ink-100 text-ink-700"
            aria-label="user menu"
          >
            <span className="w-7 h-7 rounded-full bg-brand-500 text-white text-xs flex items-center justify-center font-semibold">
              {initial}
            </span>
            <span className="text-sm">{displayName}</span>
            <IconUser />
          </button>
          <div className="hidden group-hover:block absolute right-0 mt-1 w-44 bg-white rounded-lg node-shadow border border-ink-200 py-1 z-50">
            <div className="px-3 py-2 text-sm text-ink-900 border-b border-ink-100">
              <div className="font-medium">{user?.name}</div>
              <div className="text-xs text-ink-500">{user?.id}</div>
            </div>
            <button
              onClick={logout}
              className="w-full text-left px-3 py-2 text-sm hover:bg-ink-100 text-ink-900 flex items-center gap-2"
            >
              <IconLogout /> 登出
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
