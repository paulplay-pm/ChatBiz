import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import ChatflowPage from '@/pages/ChatflowPage';

vi.mock('@/lib/apiClient', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: { workflows: [] } }),
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

describe('ChatflowPage', () => {
  it('renders chatflow page with workflow selector', () => {
    render(<ChatflowPage />, { wrapper });
    expect(screen.getByText('发送')).toBeDefined();
    expect(screen.getByText('新会话')).toBeDefined();
  });
});
