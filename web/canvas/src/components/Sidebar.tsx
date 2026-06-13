import { useNavigate, useLocation } from 'react-router-dom';
import { useUIStore } from '@/store/useUIStore';
import { MenuItem, MenuSection, Sidebar } from 'ui/index';

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

// Backwards-compatible named export for tests that import the old name.
export { AppSidebar as Sidebar };
