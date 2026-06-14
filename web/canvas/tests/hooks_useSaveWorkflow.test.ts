import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useSaveWorkflow } from '@/hooks/useSaveWorkflow';
import { api } from '@/lib/apiClient';
import { useCanvasEditStore } from '@/store/useCanvasEditStore';
import { ToastProvider } from 'ui/primitives/Toast';

vi.mock('@/lib/apiClient', () => ({
  api: {
    post: vi.fn(),
    put: vi.fn(),
  },
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(ToastProvider, null, children));
};

describe('useSaveWorkflow', () => {
  beforeEach(() => {
    useCanvasEditStore.setState({
      workflowId: null, version: 0, nodes: [], edges: [],
      dirty: false, selectedNodeId: null,
    });
  });

  it('creates a new workflow via POST when workflowId is null', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { id: 'wf-1', version: 1, name: 'new flow' },
    } as any);
    const { result } = renderHook(() => useSaveWorkflow(), { wrapper });
    const data = await result.current.mutateAsync({ name: 'new flow' });
    expect(data.id).toBe('wf-1');
    expect(data.version).toBe(1);
  });

  it('updates existing workflow via PUT when workflowId is set', async () => {
    useCanvasEditStore.setState({ workflowId: 'wf-1' });
    vi.mocked(api.put).mockResolvedValue({
      data: { id: 'wf-1', version: 2 },
    } as any);
    const { result } = renderHook(() => useSaveWorkflow(), { wrapper });
    const data = await result.current.mutateAsync({});
    expect(data.id).toBe('wf-1');
    expect(data.version).toBe(2);
  });
});
