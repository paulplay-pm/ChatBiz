import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import WorkflowListPage from '@/pages/WorkflowListPage';

vi.mock('@/lib/apiClient', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: { workflows: [], total: 0 } }),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(MemoryRouter, null, children));
};

describe('WorkflowListPage', () => {
  it('renders search and create button', async () => {
    render(<WorkflowListPage />, { wrapper });
    expect(screen.getByText('新建工作流')).toBeDefined();
    expect(screen.getByPlaceholderText('搜索工作流名称')).toBeDefined();
  });
});
