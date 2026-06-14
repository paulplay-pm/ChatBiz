import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DataPermissionsPage } from '@/views/DataPermissionsPage';
import { MOCK_RULES, MOCK_SHARES } from '@/data/dataPermissions';

describe('DataPermissionsPage', () => {
  it('3 张规则卡:个人数据(默认)/部门数据/跨部门共享', () => {
    render(<MemoryRouter><DataPermissionsPage /></MemoryRouter>);
    const cards = screen.getAllByTestId('data-rule-card');
    expect(cards).toHaveLength(3);
    expect(screen.getByText('个人数据')).toBeInTheDocument();
    expect(screen.getByText('部门数据')).toBeInTheDocument();
    expect(screen.getByText('跨部门共享')).toBeInTheDocument();
  });

  it('默认 personal 规则卡带 defaultSelected', () => {
    const personal = MOCK_RULES.find((r) => r.kind === 'personal');
    expect(personal?.defaultSelected).toBe(true);
  });

  it('4 条共享记录:销售/智能客服/产品知识库/合同', () => {
    render(<MemoryRouter><DataPermissionsPage /></MemoryRouter>);
    const rows = screen.getAllByTestId('share-row');
    expect(rows).toHaveLength(4);
    expect(screen.getByText('销售数据分析工作流')).toBeInTheDocument();
    expect(screen.getByText('智能客服 Agent')).toBeInTheDocument();
    expect(screen.getByText('产品知识库')).toBeInTheDocument();
    expect(screen.getByText('合同审核工作流')).toBeInTheDocument();
  });

  it('右上角显示「基于部门的数据隔离」badge', () => {
    render(<MemoryRouter><DataPermissionsPage /></MemoryRouter>);
    const badge = screen.getByTestId('dept-isolation-badge');
    expect(badge).toHaveTextContent('基于部门的数据隔离');
  });

  it('mock 数据:3 规则 + 4 共享,无重复', () => {
    expect(MOCK_RULES).toHaveLength(3);
    expect(MOCK_SHARES).toHaveLength(4);
    const ids = MOCK_SHARES.map((s) => s.id);
    expect(new Set(ids).size).toBe(4);
  });
});
