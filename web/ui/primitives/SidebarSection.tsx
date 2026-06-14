import { ReactNode } from 'react';

export type MenuSection = { id: string; title: string };

export function SidebarSection({ section, children }: { section: MenuSection; children: ReactNode }) {
  return (
    <div className="mb-3">
      <div data-testid={`section-title-${section.id}`} className="section-title px-3 py-1.5 text-xs font-semibold text-ink-500 uppercase tracking-wide">{section.title}</div>
      {children}
    </div>
  );
}
