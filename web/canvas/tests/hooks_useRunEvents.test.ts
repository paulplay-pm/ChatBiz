import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useRunEvents } from '@/hooks/useRunEvents';
import { useCanvasEditStore } from '@/store/useCanvasEditStore';
import { renderHook } from '@testing-library/react';

describe('useRunEvents', () => {
  beforeEach(() => {
    useCanvasEditStore.setState({
      workflowId: null, version: 0, nodes: [], edges: [],
      dirty: false, selectedNodeId: null,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('does nothing when runId is null', () => {
    const { result } = renderHook(() => useRunEvents(null));
    expect(result).toBeDefined();
  });
});
