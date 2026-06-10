import { describe, it, expect } from 'vitest';
import { autoLayout } from '../src/components/canvas/AutoLayout';
import { CanvasNode, CanvasEdge } from '../src/store/useCanvasEditStore';

describe('autoLayout', () => {
  it('should assign positions to all nodes', () => {
    const nodes: CanvasNode[] = [
      { id: 'n1', type: 'start', config: {}, position: { x: 0, y: 0 } },
      { id: 'n2', type: 'llm', config: {}, position: { x: 0, y: 100 } },
    ];
    const edges: CanvasEdge[] = [{ id: 'e1', from: 'n1', to: 'n2' }];
    const result = autoLayout(nodes, edges);
    expect(result).toHaveLength(2);
    expect(result[0].position).not.toEqual({ x: 0, y: 0 });
  });

  it('should handle empty graph', () => {
    const result = autoLayout([], []);
    expect(result).toEqual([]);
  });
});
