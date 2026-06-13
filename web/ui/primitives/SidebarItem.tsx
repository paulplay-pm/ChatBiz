export type MenuStatus = 'ready' | 'coming-soon';
export type MenuItem = { id: string; label: string; icon: string; section: string; status: MenuStatus; href: string };

export function SidebarItem({ item, active, onSelect }: { item: MenuItem; active: boolean; onSelect: (id: string) => void }) {
  return (
    <div
      data-testid={`sidebar-item-${item.id}`}
      onClick={() => onSelect(item.id)}
      className={`sidebar-item flex items-center gap-3 px-3 py-2.5 cursor-pointer text-sm ${active ? 'active bg-brand-50 text-brand-600' : 'text-ink-700 hover:bg-brand-50/50'}`}
    >
      <i className={`${item.icon} text-xs w-4`} />
      <span>{item.label}</span>
    </div>
  );
}
