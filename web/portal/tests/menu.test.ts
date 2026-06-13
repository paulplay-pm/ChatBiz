import { describe, it, expect } from 'vitest';
import { MENU, SECTIONS, MenuItem } from '@/data/menu';

describe('MENU data', () => {
  it('exports 5 sections', () => {
    expect(SECTIONS).toHaveLength(5);
  });
  it('exports 30+ menu items', () => {
    expect(MENU.length).toBeGreaterThanOrEqual(30);
  });
  it('every item status is ready or coming-soon', () => {
    for (const item of MENU as MenuItem[]) {
      expect(['ready', 'coming-soon']).toContain(item.status);
    }
  });
  it('every item has a section that exists in SECTIONS', () => {
    const sectionIds = SECTIONS.map((s) => s.id);
    for (const item of MENU) {
      expect(sectionIds).toContain(item.section);
    }
  });
});