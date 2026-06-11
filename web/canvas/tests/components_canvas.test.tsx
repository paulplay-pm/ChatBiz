import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { NodePanel } from '@/components/canvas/NodePanel';
import { ReactFlowProvider } from '@xyflow/react';
import { useCanvasEditStore } from '@/store/useCanvasEditStore';

vi.mock('@/lib/apiClient', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(MemoryRouter, null,
      React.createElement(ReactFlowProvider, null, children)));
};

describe('NodePanel', () => {
  beforeEach(() => {
    useCanvasEditStore.setState({
      workflowId: null, version: 0, nodes: [], edges: [],
      dirty: false, selectedNodeId: null,
    });
  });

  it('renders 4 categories with node items', () => {
    render(<NodePanel />, { wrapper });
    expect(screen.getByText('节点')).toBeDefined();
    expect(screen.getByText('开始 / 结束')).toBeDefined();
    expect(screen.getByText('业务节点')).toBeDefined();
    expect(screen.getByText('控制节点')).toBeDefined();
    expect(screen.getByText('集成节点')).toBeDefined();
    expect(screen.getByText('LLM')).toBeDefined();
    expect(screen.getByText('开始')).toBeDefined();
  });
});
