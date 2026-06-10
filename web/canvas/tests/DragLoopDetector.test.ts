import { describe, it, expect } from 'vitest';
import { detectCycle } from '../src/components/canvas/DragLoopDetector';

describe('detectCycle', () => {
  it('should return null for acyclic DAG', () => {
    const nodes = ['A', 'B', 'C'];
    const edges = [{ from: 'A', to: 'B' }, { from: 'B', to: 'C' }];
    expect(detectCycle(nodes, edges)).toBeNull();
  });

  it('should detect simple 2-node cycle', () => {
    const nodes = ['A', 'B'];
    const edges = [{ from: 'A', to: 'B' }, { from: 'B', to: 'A' }];
    expect(detectCycle(nodes, edges)).not.toBeNull();
  });

  it('should detect 3-node cycle', () => {
    const nodes = ['A', 'B', 'C'];
    const edges = [{ from: 'A', to: 'B' }, { from: 'B', to: 'C' }, { from: 'C', to: 'A' }];
    expect(detectCycle(nodes, edges)).not.toBeNull();
  });

  it('should return null for multi-branch DAG', () => {
    const nodes = ['A', 'B', 'C', 'D'];
    const edges = [{ from: 'A', to: 'B' }, { from: 'A', to: 'C' }, { from: 'B', to: 'D' }, { from: 'C', to: 'D' }];
    expect(detectCycle(nodes, edges)).toBeNull();
  });

  it('should return null for empty graph', () => {
    expect(detectCycle([], [])).toBeNull();
  });

  it('should detect cycle with self-loop', () => {
    const nodes = ['A', 'B'];
    const edges = [{ from: 'A', to: 'B' }, { from: 'B', to: 'B' }];
    expect(detectCycle(nodes, edges)).not.toBeNull();
  });
});
