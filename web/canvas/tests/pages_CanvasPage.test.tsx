import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import CanvasPage from '@/pages/CanvasPage';
import { useCanvasEditStore, type CanvasNode } from '@/store/useCanvasEditStore';
import { ToastProvider } from 'ui/primitives/Toast';

vi.mock('@/lib/apiClient', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: { id: 'w1', version: 1, definition_json: { nodes: [], edges: [] } } }),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(MemoryRouter, { initialEntries: ['/workflows/w1/edit'] },
      React.createElement(ToastProvider, null, children)));
};

function seedTwoNodes() {
  // 在 store 注入 2 个节点 A、B
  useCanvasEditStore.getState().setInitial('w1', 1, [
    { id: 'A', type: 'llm', config: {}, position: { x: 0, y: 0 } } as CanvasNode,
    { id: 'B', type: 'code', config: {}, position: { x: 100, y: 0 } } as CanvasNode,
  ], []);
}

describe('CanvasPage (V3 既有)', () => {
  it('renders canvas with node panel', () => {
    render(<CanvasPage />, { wrapper });
    expect(screen.getByText('节点')).toBeDefined();
    expect(screen.getByText('自动布局')).toBeDefined();
    expect(screen.getByText('保存')).toBeDefined();
  });
});

describe('CanvasPage __rfConnect hook 行为 (V5 T4 防漂移)', () => {
  beforeEach(() => {
    // 重置 store
    useCanvasEditStore.setState({
      workflowId: null,
      version: 0,
      nodes: [],
      edges: [],
      dirty: false,
      selectedNodeId: null,
    });
  });

  it('正常连接:hook({source, target}) 走 onConnect 同步路径,edges 新增 1 条', () => {
    seedTwoNodes();
    render(<CanvasPage />, { wrapper });
    // dev 模式 hook 已被 CanvasPage useEffect 挂载
    expect(typeof (window as unknown as { __rfConnect?: unknown }).__rfConnect).toBe('function');

    act(() => {
      (window as unknown as { __rfConnect: (a: { source: string; target: string }) => void }).__rfConnect({ source: 'A', target: 'B' });
    });

    const edges = useCanvasEditStore.getState().edges;
    expect(edges).toHaveLength(1);
    expect(edges[0]?.from).toBe('A');
    expect(edges[0]?.to).toBe('B');
  });

  it('自连接拒绝:hook({A, A}) 不变更 edges(防 drag-loop 自连边界)', () => {
    seedTwoNodes();
    render(<CanvasPage />, { wrapper });
    const before = useCanvasEditStore.getState().edges.length;

    act(() => {
      (window as unknown as { __rfConnect: (a: { source: string; target: string }) => void }).__rfConnect({ source: 'A', target: 'A' });
    });

    const after = useCanvasEditStore.getState().edges.length;
    expect(after).toBe(before);
  });

  it('循环拒绝:hook({C, A}) 已有 edge A→B→C 时不新增(防 cycle 边界)', () => {
    seedTwoNodes();
    // 加第三个节点 C,先建 A→B + B→C,再尝试 C→A
    useCanvasEditStore.getState().setInitial('w1', 1, [
      { id: 'A', type: 'llm', config: {}, position: { x: 0, y: 0 } } as CanvasNode,
      { id: 'B', type: 'code', config: {}, position: { x: 100, y: 0 } } as CanvasNode,
      { id: 'C', type: 'llm', config: {}, position: { x: 200, y: 0 } } as CanvasNode,
    ], [
      { id: 'e1', from: 'A', to: 'B' },
      { id: 'e2', from: 'B', to: 'C' },
    ]);
    render(<CanvasPage />, { wrapper });
    const before = useCanvasEditStore.getState().edges.length;

    act(() => {
      (window as unknown as { __rfConnect: (a: { source: string; target: string }) => void }).__rfConnect({ source: 'C', target: 'A' });
    });

    const after = useCanvasEditStore.getState().edges.length;
    expect(after).toBe(before);
  });
});
