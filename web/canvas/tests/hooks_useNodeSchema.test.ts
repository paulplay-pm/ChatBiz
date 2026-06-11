import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useNodeSchema } from '@/hooks/useNodeSchema';
import { api } from '@/lib/apiClient';

// Mock the api module
vi.mock('@/lib/apiClient', () => ({
  api: {
    get: vi.fn(),
  },
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return React.createElement(QueryClientProvider, { client: qc }, children);
};

describe('useNodeSchema', () => {
  it('does not fetch when type is null', () => {
    const { result } = renderHook(() => useNodeSchema(null), { wrapper });
    // When enabled=false, query doesn't run; data stays undefined
    expect(result.current.data).toBeUndefined();
  });

  it('fetches schema for a given type', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: { type: 'llm', version: '1.0.0', config_schema: { properties: {} } },
    } as any);
    const { result } = renderHook(() => useNodeSchema('llm'), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({
      type: 'llm',
      version: '1.0.0',
      config_schema: { properties: {} },
    });
  });
});
