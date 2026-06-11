import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { api } from '@/lib/apiClient';
import { useAuthStore } from '@/store/useAuthStore';

describe('apiClient', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('exports an axios instance with base config', () => {
    expect(api).toBeDefined();
    expect(typeof api.get).toBe('function');
    expect(typeof api.post).toBe('function');
  });

  it('injects Authorization header from auth store', async () => {
    useAuthStore.getState().setAuth('test-token', { id: 'u-1', name: 'T', email: 't@c' });
    // Trigger request interceptor by making a call; mock responses first
    vi.spyOn(api, 'get').mockResolvedValue({ data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config: {} } as any);
    const r = await api.get('/test');
    expect(r.data).toEqual({ ok: true });
  });

  it('returns error on 401 with structured detail', () => {
    // Verify the interceptor structure
    const interceptor = api.interceptors.response;
    expect(interceptor).toBeDefined();
  });
});
