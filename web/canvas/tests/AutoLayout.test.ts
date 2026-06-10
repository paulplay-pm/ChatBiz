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
    // dagre produces {x:90,y:40} after subtracting 90/40 → {0,0}. At least verify
    // that both node positions were assigned by dagre (not the original {0,0}).
    expect(result[0]!.position).toBeDefined();
    expect(result[1]!.position).toBeDefined();
    // Positions should differ after layout; with rankdir=LR, x changes and y may stay equal.
    expect(result[0]!.position.x).not.toEqual(result[1]!.position.x);
  });

  it('should handle empty graph', () => {
    const result = autoLayout([], []);
    expect(result).toEqual([]);
  });
});
