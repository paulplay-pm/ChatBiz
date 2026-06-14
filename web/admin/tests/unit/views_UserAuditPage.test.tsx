import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { UserAuditPage } from '@/views/UserAuditPage';
import { MOCK_USERS } from '@/data/users';

describe('UserAuditPage', () => {
  it('只显示 status=pending 的行(王五 1 行)', () => {
    render(<MemoryRouter><UserAuditPage /></MemoryRouter>);
    expect(screen.getAllByTestId('audit-row')).toHaveLength(1);
  });

  it('待审核 badge 显示数量 1', () => {
    render(<MemoryRouter><UserAuditPage /></MemoryRouter>);
    const badge = screen.getByTestId('pending-badge');
    expect(badge).toHaveTextContent('1');
  });

  it('每行含通过/拒绝两个按钮', () => {
    render(<MemoryRouter><UserAuditPage /></MemoryRouter>);
    expect(screen.getAllByTestId('audit-approve')).toHaveLength(1);
    expect(screen.getAllByTestId('audit-reject')).toHaveLength(1);
  });

  it('mock 数据:3 行中 1 行 pending', () => {
    const pending = MOCK_USERS.filter((u) => u.status === 'pending');
    expect(pending).toHaveLength(1);
    expect(pending[0]?.name).toBe('王五');
  });
});
