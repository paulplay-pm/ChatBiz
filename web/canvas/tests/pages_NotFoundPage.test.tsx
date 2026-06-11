import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import NotFoundPage from '@/pages/NotFoundPage';

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient();
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(MemoryRouter, null, children));
};

describe('NotFoundPage', () => {
  it('renders 404 message', () => {
    render(<NotFoundPage />, { wrapper });
    expect(screen.getByText('404')).toBeDefined();
    expect(screen.getByText('页面不存在')).toBeDefined();
  });
});
