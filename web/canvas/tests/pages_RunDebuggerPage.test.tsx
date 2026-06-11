import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// Polyfill EventSource for jsdom
beforeAll(() => {
  (globalThis as any).EventSource = class {
    url: string;
    onerror: (() => void) | null = null;
    listeners: Record<string, ((e: any) => void)[]> = {};
    constructor(url: string) { this.url = url; }
    addEventListener(name: string, cb: any) {
      if (!this.listeners[name]) this.listeners[name] = [];
      this.listeners[name].push(cb);
    }
    close() {}
  };
});

vi.mock('@/lib/apiClient', () => ({
  api: {
    get: vi.fn().mockResolvedValue({
      data: {
        run_id: 'r1',
        workflow_id: 'w1',
        workflow_version: 1,
        thread_id: 'thread-1',
        mode: 'workflow',
        status: 'completed',
        started_by: 'u-1',
        started_at: '2026-06-11T10:00:00',
        ended_at: '2026-06-11T10:01:00',
        error_class: null,
        error_message: null,
        events: [],
      },
    }),
  },
}));

import RunDebuggerPage from '@/pages/RunDebuggerPage';

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient();
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(MemoryRouter, { initialEntries: ['/runs/r1'] },
      React.createElement(Routes, null,
        React.createElement(Route, { path: '/runs/:runId', element: children as any })),
    ));
};

describe('RunDebuggerPage', () => {
  it('renders run debug info', async () => {
    render(<RunDebuggerPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText('completed')).toBeDefined();
    });
  });
});
