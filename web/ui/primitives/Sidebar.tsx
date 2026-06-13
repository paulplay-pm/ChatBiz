import { MenuItem, SidebarItem } from './SidebarItem';
import { MenuSection, SidebarSection } from './SidebarSection';

export function Sidebar({ items, sections, activeId, onSelect }: {
  items: MenuItem[]; sections: MenuSection[]; activeId: string; onSelect: (id: string) => void;
}) {
  return (
    <aside data-testid="sidebar" className="w-64 bg-white border-r border-ink-200 flex flex-col h-full overflow-y-auto">
      {sections.map((s) => (
        <SidebarSection key={s.id} section={s}>
          {items.filter((i) => i.section === s.id).map((i) => (
            <SidebarItem key={i.id} item={i} active={i.id === activeId} onSelect={onSelect} />
          ))}
        </SidebarSection>
      ))}
    </aside>
  );
}
