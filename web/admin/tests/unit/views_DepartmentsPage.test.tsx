import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DepartmentsPage } from '@/views/DepartmentsPage';
import { MOCK_DEPARTMENTS } from '@/data/departments';

describe('DepartmentsPage', () => {
  it('渲染 3 个顶级部门', () => {
    render(<MemoryRouter><DepartmentsPage /></MemoryRouter>);
    const topLevel = MOCK_DEPARTMENTS.length;
    const nodes = screen.getAllByTestId('dept-node');
    // 3 顶级 + 2 子(技术部 → 后端 + 前端)
    expect(nodes).toHaveLength(topLevel + 2);
  });

  it('技术部下含 2 个子部门', () => {
    render(<MemoryRouter><DepartmentsPage /></MemoryRouter>);
    expect(screen.getByText('技术部')).toBeInTheDocument();
    expect(screen.getByText('后端开发组')).toBeInTheDocument();
    expect(screen.getByText('前端开发组')).toBeInTheDocument();
  });

  it('顶级部门:技术部/产品部/运营部', () => {
    render(<MemoryRouter><DepartmentsPage /></MemoryRouter>);
    expect(screen.getByText('技术部')).toBeInTheDocument();
    expect(screen.getByText('产品部')).toBeInTheDocument();
    expect(screen.getByText('运营部')).toBeInTheDocument();
  });

  it('每部门显示 +N 成员数 badge', () => {
    render(<MemoryRouter><DepartmentsPage /></MemoryRouter>);
    const counts = screen.getAllByTestId('dept-member-count');
    // 3 顶级 + 2 子 = 5 个
    expect(counts).toHaveLength(5);
  });

  it('右上角 + 添加部门 按钮', () => {
    render(<MemoryRouter><DepartmentsPage /></MemoryRouter>);
    expect(screen.getByTestId('add-department')).toBeInTheDocument();
  });

  it('mock 树状:3 顶级 + 1 顶级带 2 子', () => {
    expect(MOCK_DEPARTMENTS).toHaveLength(3);
    const tech = MOCK_DEPARTMENTS.find((d) => d.id === 'd-tech');
    expect(tech?.children).toHaveLength(2);
  });
});
