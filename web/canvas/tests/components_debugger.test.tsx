import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { NodeEventTimeline } from '@/components/debugger/NodeEventTimeline';
import { RetryCancelButtons } from '@/components/debugger/RetryCancelButtons';
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

const sampleEvents = [
  { id: 1, node_id: 'n1', status: 'completed', started_at: '2026-06-11T10:00:00', ended_at: '2026-06-11T10:00:30', error_class: null, error_message: null },
  { id: 2, node_id: 'n2', status: 'failed', started_at: '2026-06-11T10:00:30', ended_at: '2026-06-11T10:00:31', error_class: 'UserError', error_message: 'bad input' },
];

describe('NodeEventTimeline', () => {
  it('renders timeline items', () => {
    render(<NodeEventTimeline events={sampleEvents} />, { wrapper });
    expect(screen.getByText('completed')).toBeDefined();
    expect(screen.getByText('failed')).toBeDefined();
  });

  it('shows error info for failed events', () => {
    render(<NodeEventTimeline events={sampleEvents} />, { wrapper });
    expect(screen.getAllByText(/UserError/).length).toBeGreaterThan(0);
  });
});

describe('RetryCancelButtons', () => {
  it('renders retry and cancel buttons', () => {
    render(<RetryCancelButtons workflowId="wf-1" />, { wrapper });
    expect(screen.getByText('重试')).toBeDefined();
    expect(screen.getByText('取消')).toBeDefined();
  });
});
