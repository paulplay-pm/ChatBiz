import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import LoginPage from '@/pages/LoginPage';

vi.mock('@/lib/apiClient', () => ({
  api: {
    post: vi.fn().mockResolvedValue({ data: { token: 'ok', user: { id: 'u', name: 'P', email: 'p@c' } } }),
  },
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient();
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(MemoryRouter, null, children));
};

describe('LoginPage', () => {
  it('renders login form', () => {
    render(<LoginPage />, { wrapper });
    expect(screen.getByText('ChatBiz 登录')).toBeDefined();
    expect(screen.getByText('用户名')).toBeDefined();
  });
});
