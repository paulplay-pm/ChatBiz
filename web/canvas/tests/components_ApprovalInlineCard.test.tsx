import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { ApprovalInlineCard } from '@/components/chatflow/ApprovalInlineCard';
import { useAuthStore } from '@/store/useAuthStore';
import { ToastProvider } from 'ui/primitives/Toast';

vi.mock('@/lib/apiClient', () => ({
  api: { post: vi.fn() },
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient();
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(MemoryRouter, null,
      React.createElement(ToastProvider, null, children)));
};

describe('ApprovalInlineCard', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null });
  });

  it('shows waiting message when user is not approver', () => {
    useAuthStore.setState({ token: 'x', user: { id: 'u-2', name: 'Bob', email: 'b@c' } });
    render(
      React.createElement(ApprovalInlineCard, {
        approvalId: 'a1',
        approverUserId: 'u-1',
        content: 'approve budget',
        onResolved: vi.fn(),
      }),
      { wrapper },
    );
    expect(screen.getByText(/等待/)).toBeDefined();
  });

  it('shows approve/reject buttons when user is approver', () => {
    useAuthStore.setState({ token: 'x', user: { id: 'u-1', name: 'Alice', email: 'a@c' } });
    render(
      React.createElement(ApprovalInlineCard, {
        approvalId: 'a1',
        approverUserId: 'u-1',
        content: 'approve budget',
        onResolved: vi.fn(),
      }),
      { wrapper },
    );
    // Ant Design renders button text in span nodes; just verify element count
    expect(screen.getAllByText('批准').length).toBeGreaterThan(0);
    expect(screen.getAllByText('拒绝').length).toBeGreaterThan(0);
  });
});
