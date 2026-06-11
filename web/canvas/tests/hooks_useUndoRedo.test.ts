import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useUndoRedo } from '@/hooks/useUndoRedo';
import { useCanvasEditStore } from '@/store/useCanvasEditStore';
import { renderHook } from '@testing-library/react';

describe('useUndoRedo', () => {
  beforeEach(() => {
    useCanvasEditStore.setState({
      workflowId: null, version: 0, nodes: [], edges: [],
      dirty: false, selectedNodeId: null,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('registers and removes keydown listener', () => {
    const addSpy = vi.spyOn(window, 'addEventListener');
    const removeSpy = vi.spyOn(window, 'removeEventListener');
    const { unmount } = renderHook(() => useUndoRedo());
    expect(addSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
    unmount();
    expect(removeSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
  });
});
