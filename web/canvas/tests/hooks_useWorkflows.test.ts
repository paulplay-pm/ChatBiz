import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useWorkflows, useCreateWorkflow, useDeleteWorkflow } from '@/hooks/useWorkflows';
import { api } from '@/lib/apiClient';

vi.mock('@/lib/apiClient', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return React.createElement(QueryClientProvider, { client: qc }, children);
};

describe('useWorkflows', () => {
  it('fetches workflow list', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { workflows: [], total: 0 },
    });
    const { result } = renderHook(
      () => useWorkflows({ search: '', page: 1, page_size: 20 }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ workflows: [], total: 0 });
  });
});

describe('useCreateWorkflow', () => {
  it('posts to create and invalidates', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: { id: 'wf-1', version: 1, name: 'test' },
    });
    const { result } = renderHook(() => useCreateWorkflow(), { wrapper });
    const data = await result.current.mutateAsync({
      name: 'test',
      definition_json: { nodes: [], edges: [], variables: {}, mode: 'workflow' },
    });
    expect(data).toEqual({ id: 'wf-1', version: 1, name: 'test' });
  });
});

describe('useDeleteWorkflow', () => {
  it('deletes and invalidates', async () => {
    vi.mocked(api.delete).mockResolvedValue({ data: { ok: true } });
    const { result } = renderHook(() => useDeleteWorkflow(), { wrapper });
    const data = await result.current.mutateAsync('wf-1');
    expect(data).toEqual({ ok: true });
  });
});
