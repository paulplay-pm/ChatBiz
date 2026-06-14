import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RolesPage } from '@/views/RolesPage';
import { MOCK_ROLES } from '@/data/roles';

describe('RolesPage', () => {
  it('渲染 4 个角色卡', () => {
    render(<MemoryRouter><RolesPage /></MemoryRouter>);
    expect(screen.getAllByTestId('role-card')).toHaveLength(4);
  });

  it('4 角色名称:超管/部门管理员/开发者/普通用户', () => {
    render(<MemoryRouter><RolesPage /></MemoryRouter>);
    expect(screen.getByText('超级管理员')).toBeInTheDocument();
    expect(screen.getByText('部门管理员')).toBeInTheDocument();
    expect(screen.getByText('开发者')).toBeInTheDocument();
    expect(screen.getByText('普通用户')).toBeInTheDocument();
  });

  it('蓝色 info bar 显示提示文案', () => {
    render(<MemoryRouter><RolesPage /></MemoryRouter>);
    const bar = screen.getByText(/一个用户可拥有多个角色/);
    expect(bar).toBeInTheDocument();
  });

  it('默认显示 super-admin 的权限矩阵', () => {
    render(<MemoryRouter><RolesPage /></MemoryRouter>);
    const matrix = screen.getByTestId('role-matrix');
    expect(matrix).toHaveTextContent('超级管理员');
    // 10 操作位(workflow + conversation × 5 操作),super-admin 全 true
    expect(screen.getAllByTestId('matrix-check')).toHaveLength(10);
  });

  it('mock 4 角色 + matrix 维度对齐', () => {
    expect(MOCK_ROLES).toHaveLength(4);
    for (const role of MOCK_ROLES) {
      expect(role.memberAvatars.length).toBeGreaterThanOrEqual(3);
    }
  });
});
