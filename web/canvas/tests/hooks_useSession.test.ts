import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useSession } from '@/hooks/useSession';
import { renderHook, act } from '@testing-library/react';

// localStorage mock
const storage = new Map<string, string>();
const localStorageMock = {
  getItem: vi.fn((key: string) => storage.get(key) ?? null),
  setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
  removeItem: vi.fn((key: string) => storage.delete(key)),
  clear: vi.fn(() => storage.clear()),
};

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// location hash mock
let hashValue = '';
Object.defineProperty(window, 'location', {
  value: {
    get hash() {
      return hashValue;
    },
    set hash(v: string) {
      hashValue = v;
    },
  },
  writable: true,
});

describe('useSession', () => {
  beforeEach(() => {
    storage.clear();
    hashValue = '';
    vi.clearAllMocks();
  });

  it('generates a new session id when none stored', () => {
    const { result } = renderHook(() => useSession());
    expect(result.current.sessionId).toBeTruthy();
    expect(typeof result.current.sessionId).toBe('string');
    // Should be a UUID format
    expect(result.current.sessionId).toMatch(/^[0-9a-f-]+$/);
  });

  it('reuses stored session id from localStorage', () => {
    storage.set('chatbiz-session-id', 'cached-session-123');
    const { result } = renderHook(() => useSession());
    expect(result.current.sessionId).toBe('cached-session-123');
  });

  it('sets URL hash with session id', () => {
    const { result } = renderHook(() => useSession());
    expect(hashValue).toContain(`session=${result.current.sessionId}`);
  });

  it('newSession creates a fresh id', () => {
    storage.set('chatbiz-session-id', 'old-id');
    const { result } = renderHook(() => useSession());
    act(() => {
      result.current.newSession();
    });
    const newId = result.current.sessionId;
    expect(newId).not.toBe('old-id');
    expect(storage.get('chatbiz-session-id')).toBe(newId);
  });
});
