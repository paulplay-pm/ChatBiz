import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PermissionsPage } from '@/views/PermissionsPage';
import { MOCK_MODULES, PERMISSION_ACTIONS, ROLE_OPTIONS } from '@/data/permissions';

describe('PermissionsPage', () => {
  it('7 模块 11 权限点 + 6 操作列', () => {
    render(<MemoryRouter><PermissionsPage /></MemoryRouter>);
    const rows = screen.getAllByTestId('permission-row');
    // 11 权限点行
    expect(rows).toHaveLength(11);
    expect(MOCK_MODULES).toHaveLength(7);
    const totalPoints = MOCK_MODULES.reduce((acc, m) => acc + m.points.length, 0);
    expect(totalPoints).toBe(11);
    expect(PERMISSION_ACTIONS).toHaveLength(6);
  });

  it('4 角色 dropdown 选项', () => {
    render(<MemoryRouter><PermissionsPage /></MemoryRouter>);
    const select = screen.getByTestId('role-select') as HTMLSelectElement;
    expect(ROLE_OPTIONS).toHaveLength(4);
    expect(select.options).toHaveLength(4);
  });

  it('默认 super-admin + 只读 toggle ON', () => {
    render(<MemoryRouter><PermissionsPage /></MemoryRouter>);
    const select = screen.getByTestId('role-select') as HTMLSelectElement;
    expect(select.value).toBe('super-admin');
    const toggle = screen.getByTestId('readonly-toggle') as HTMLInputElement;
    expect(toggle.checked).toBe(true);
  });

  it('所有 checkbox disabled(V4 接 API 后才能写)', () => {
    render(<MemoryRouter><PermissionsPage /></MemoryRouter>);
    const cells = screen.getAllByTestId('permission-cell');
    expect(cells.length).toBe(11 * 6);
    for (const c of cells) {
      expect(c).toBeDisabled();
    }
  });

  it('super-admin 11 点 × 6 操作 = 66 cell,全部 checked', () => {
    render(<MemoryRouter><PermissionsPage /></MemoryRouter>);
    const cells = screen.getAllByTestId('permission-cell');
    const checked = cells.filter(
      (c) => c.getAttribute('data-allowed') === 'true',
    );
    expect(checked).toHaveLength(11 * 6);
  });

  it('切换角色到 normal-user → 大部分 cell 取消', () => {
    render(<MemoryRouter><PermissionsPage /></MemoryRouter>);
    const select = screen.getByTestId('role-select');
    fireEvent.change(select, { target: { value: 'normal-user' } });
    const cells = screen.getAllByTestId('permission-cell');
    const allowed = cells.filter(
      (c) => c.getAttribute('data-allowed') === 'true',
    );
    // normal-user 11 点 × 仅 view = 11 allowed
    expect(allowed).toHaveLength(11);
  });
});
