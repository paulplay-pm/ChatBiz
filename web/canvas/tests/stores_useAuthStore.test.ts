import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from '@/store/useAuthStore';

describe('useAuthStore', () => {
  beforeEach(() => {
    // Reset store state between tests
    useAuthStore.setState({ token: null, user: null });
  });

  it('initial state has null token and user', () => {
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
  });

  it('setAuth sets token and user', () => {
    useAuthStore.getState().setAuth('my-token', { id: 'u-1', name: 'Alice', email: 'alice@chatbiz' });
    const state = useAuthStore.getState();
    expect(state.token).toBe('my-token');
    expect(state.user).toEqual({ id: 'u-1', name: 'Alice', email: 'alice@chatbiz' });
  });

  it('clear resets to null', () => {
    useAuthStore.getState().setAuth('tok', { id: 'u-2', name: 'Bob', email: 'bob@c' });
    useAuthStore.getState().clear();
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
  });
});
