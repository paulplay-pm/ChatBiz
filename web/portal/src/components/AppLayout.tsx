import { Outlet, useNavigate } from 'react-router-dom';
import { Sidebar } from '@/components/primitives/Sidebar';
import { MenuItem, MenuSection } from '@/data/menu';

export function AppLayout({ menuItems, sections, activeId }: {
  menuItems: MenuItem[]; sections: MenuSection[]; activeId: string;
}) {
  const nav = useNavigate();
  const handleSelect = (id: string) => {
    const item = menuItems.find((i) => i.id === id);
    if (item) {
      if (item.href.startsWith('/canvas/') || item.href.startsWith('/admin/')) {
        window.location.assign(`http://localhost:5173${item.href}`);
      } else {
        nav(item.href);
      }
    }
  };
  return (
    <div className="flex h-screen">
      <Sidebar items={menuItems} sections={sections} activeId={activeId} onSelect={handleSelect} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <header data-testid="header" className="glass h-14 flex items-center justify-between px-4 flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white font-bold">C</div>
          <div className="text-sm text-ink-500">ChatBiz Portal</div>
        </header>
        <main className="flex-1 overflow-y-auto bg-ink-50">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
