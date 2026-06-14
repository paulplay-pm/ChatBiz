import { describe, it, expect } from 'vitest';
import { MENU, SECTIONS, MenuItem } from '@/data/menu';

describe('MENU data (V3 5 分组)', () => {
  it('exports 5 sections (工作区/探索/配置中心/运维/系统管理)', () => {
    expect(SECTIONS).toHaveLength(5);
    const titles = SECTIONS.map((s) => s.title);
    expect(titles).toEqual(['工作区', '探索', '配置中心', '运维', '系统管理']);
  });
  it('exports 24 menu items', () => {
    expect(MENU).toHaveLength(24);
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
  it('every item has the external boolean field', () => {
    for (const item of MENU) {
      expect(typeof item.external).toBe('boolean');
    }
  });
  it('系统管理分组 6 项全部 external: true (跳 /admin/<sub>)', () => {
    const systemItems = MENU.filter((m) => m.section === 'system');
    expect(systemItems).toHaveLength(6);
    for (const item of systemItems) {
      expect(item.external).toBe(true);
      expect(item.href).toMatch(/^\/admin\//);
    }
  });
  it('canvas 跨跳 3 项(workflow-list/chatflow/agent-list)external: true', () => {
    const canvasItems = MENU.filter((m) => m.external && m.href.startsWith('/canvas/'));
    expect(canvasItems.length).toBeGreaterThanOrEqual(3);
    for (const item of canvasItems) {
      expect(item.external).toBe(true);
    }
  });
  it('工作台 (dashboard) 是 internal 唯一入口', () => {
    const dash = MENU.find((m) => m.id === 'dashboard');
    expect(dash).toBeDefined();
    expect(dash!.external).toBe(false);
    expect(dash!.href).toBe('/');
  });
});
