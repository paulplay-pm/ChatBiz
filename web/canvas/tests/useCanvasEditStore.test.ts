import { describe, it, expect } from 'vitest';
import { useCanvasEditStore } from '../src/store/useCanvasEditStore';

describe('useCanvasEditStore', () => {
  it('should add nodes and mark dirty', () => {
    const { addNode, nodes } = useCanvasEditStore.getState();
    expect(nodes).toHaveLength(0);
    addNode({ id: 'n1', type: 'llm', config: { model: 'gpt-4' }, position: { x: 100, y: 200 } });
    const state = useCanvasEditStore.getState();
    expect(state.nodes).toHaveLength(1);
    expect(state.dirty).toBe(true);
    expect(state.nodes[0]!.type).toBe('llm');
  });

  it('should remove nodes and associated edges', () => {
    const store = useCanvasEditStore.getState();
    store.setInitial('wf-1', 1, [
      { id: 'n1', type: 'start', config: {}, position: { x: 0, y: 0 } },
      { id: 'n2', type: 'end', config: {}, position: { x: 200, y: 0 } },
    ], [{ id: 'e1', from: 'n1', to: 'n2' }]);
    const s1 = useCanvasEditStore.getState();
    expect(s1.nodes).toHaveLength(2);
    expect(s1.edges).toHaveLength(1);

    s1.removeNode('n1');
    const s2 = useCanvasEditStore.getState();
    expect(s2.nodes).toHaveLength(1);
    expect(s2.edges).toHaveLength(0);
  });

  it('should add edges', () => {
    const store = useCanvasEditStore.getState();
    store.setInitial('wf-2', 1, [
      { id: 'n1', type: 'start', config: {}, position: { x: 0, y: 0 } },
      { id: 'n2', type: 'end', config: {}, position: { x: 200, y: 0 } },
    ], []);
    store.addEdge({ id: 'e1', from: 'n1', to: 'n2' });
    expect(useCanvasEditStore.getState().edges).toHaveLength(1);
  });

  it('should track node status', () => {
    const store = useCanvasEditStore.getState();
    store.setInitial('wf-3', 1, [{ id: 'n1', type: 'llm', config: {}, position: { x: 0, y: 0 } }], []);
    store.setNodeStatus('n1', 'running');
    expect(useCanvasEditStore.getState().nodes[0]!.status).toBe('running');
    store.setNodeStatus('n1', 'completed');
    expect(useCanvasEditStore.getState().nodes[0]!.status).toBe('completed');
  });

  it('should mark clean', () => {
    const store = useCanvasEditStore.getState();
    store.setInitial('wf-4', 1, [], []);
    store.addNode({ id: 'n1', type: 'start', config: {}, position: { x: 0, y: 0 } });
    expect(useCanvasEditStore.getState().dirty).toBe(true);
    store.markClean();
    expect(useCanvasEditStore.getState().dirty).toBe(false);
  });
});
