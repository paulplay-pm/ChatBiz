import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { useDebounce } from '@/hooks/useDebounce';
import { renderHook, act } from '@testing-library/react';

describe('useDebounce', () => {
  // Enable fake timers for debounce tests
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('hello', 200));
    expect(result.current).toBe('hello');
  });

  it('returns old value before delay and new value after delay', () => {
    const { result, rerender } = renderHook(
      ({ v }: { v: string }) => useDebounce(v, 300),
      { initialProps: { v: 'first' } },
    );
    expect(result.current).toBe('first');
    rerender({ v: 'second' });
    // still old immediately
    expect(result.current).toBe('first');
    act(() => {
      vi.advanceTimersByTime(300);
    });
    expect(result.current).toBe('second');
  });

  it('resets timer when value changes before delay', () => {
    const { result, rerender } = renderHook(
      ({ v }: { v: string }) => useDebounce(v, 500),
      { initialProps: { v: 'a' } },
    );
    rerender({ v: 'b' });
    act(() => {
      vi.advanceTimersByTime(200); // partial
    });
    rerender({ v: 'c' });
    act(() => {
      vi.advanceTimersByTime(200); // still not expired for 'c'
    });
    expect(result.current).toBe('a');
    act(() => {
      vi.advanceTimersByTime(300); // now expired
    });
    expect(result.current).toBe('c');
  });

  it('clears timeout on unmount', () => {
    const clearSpy = vi.spyOn(window, 'clearTimeout');
    const { unmount } = renderHook(() => useDebounce('x', 200));
    unmount();
    // clearTimeout should have been called via useEffect cleanup
    expect(clearSpy).toHaveBeenCalled();
    clearSpy.mockRestore();
  });
});
