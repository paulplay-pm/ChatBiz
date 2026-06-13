import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Sidebar } from '@/components/primitives/Sidebar';
import { MENU, SECTIONS } from '@/data/menu';

describe('Sidebar', () => {
  it('renders 5 section titles', () => {
    render(<Sidebar items={MENU} sections={SECTIONS} activeId="dashboard" onSelect={() => {}} />);
    SECTIONS.forEach((s) => expect(screen.getByTestId(`section-title-${s.id}`)).toBeInTheDocument());
  });
  it('renders all menu items', () => {
    render(<Sidebar items={MENU} sections={SECTIONS} activeId="dashboard" onSelect={() => {}} />);
    expect(screen.getAllByTestId(/^sidebar-item-/)).toHaveLength(MENU.length);
  });
  it('highlights active item', () => {
    render(<Sidebar items={MENU} sections={SECTIONS} activeId="workflow-list" onSelect={() => {}} />);
    expect(screen.getByTestId('sidebar-item-workflow-list').className).toMatch(/bg-brand-50/);
  });
});