import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import CanvasPage from '@/pages/CanvasPage';
import { ToastProvider } from 'ui/primitives/Toast';

vi.mock('@/lib/apiClient', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: { id: 'w1', version: 1, definition_json: { nodes: [], edges: [] } } }),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(MemoryRouter, { initialEntries: ['/workflows/w1/edit'] },
      React.createElement(ToastProvider, null, children)));
};

describe('CanvasPage', () => {
  it('renders canvas with node panel', () => {
    render(<CanvasPage />, { wrapper });
    expect(screen.getByText('节点')).toBeDefined();
    expect(screen.getByText('自动布局')).toBeDefined();
    expect(screen.getByText('保存')).toBeDefined();
  });
});
