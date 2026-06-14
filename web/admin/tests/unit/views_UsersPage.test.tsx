import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { UsersPage } from '@/views/UsersPage';
import { MOCK_USERS } from '@/data/users';

describe('UsersPage', () => {
  it('渲染 3 行 mock 用户', () => {
    render(<MemoryRouter><UsersPage /></MemoryRouter>);
    expect(screen.getAllByTestId('user-row')).toHaveLength(3);
  });

  it('6 列定义:用户/部门/角色/状态/最后登录/操作', () => {
    render(<MemoryRouter><UsersPage /></MemoryRouter>);
    const headers = screen.getAllByRole('columnheader');
    expect(headers).toHaveLength(6);
    expect(headers[0]).toHaveTextContent('用户');
    expect(headers[1]).toHaveTextContent('部门');
    expect(headers[2]).toHaveTextContent('角色');
    expect(headers[3]).toHaveTextContent('状态');
    expect(headers[4]).toHaveTextContent('最后登录');
    expect(headers[5]).toHaveTextContent('操作');
  });

  it('工具栏含搜索/批量导入/导出/添加用户', () => {
    render(<MemoryRouter><UsersPage /></MemoryRouter>);
    expect(screen.getByPlaceholderText('搜索姓名 / 邮箱')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '批量导入' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '导出' })).toBeInTheDocument();
    expect(screen.getByTestId('add-user')).toBeInTheDocument();
  });

  it('status 渲染:1 个 active + 1 个 active + 1 个 pending', () => {
    render(<MemoryRouter><UsersPage /></MemoryRouter>);
    const statuses = screen.getAllByTestId('user-status');
    expect(statuses).toHaveLength(3);
    const labels = statuses.map((s) => s.textContent);
    expect(labels).toEqual(['正常', '正常', '待审核']);
  });

  it('数据来源:mock 3 行,无 fetch 调用', () => {
    expect(MOCK_USERS).toHaveLength(3);
  });
});
