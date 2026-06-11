import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { ConfigPanel } from '@/components/canvas/ConfigPanel';
import { useCanvasEditStore } from '@/store/useCanvasEditStore';
import { ReactFlowProvider } from '@xyflow/react';

vi.mock('@/lib/apiClient', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

// Mock useNodeSchema to return a real RJSF-compatible schema
vi.mock('@/hooks/useNodeSchema', () => ({
  useNodeSchema: vi.fn(() => ({
    data: {
      type: 'llm',
      version: '1.0.0',
      config_schema: {
        type: 'object',
        required: ['model'],
        properties: {
          model: { type: 'string', title: 'Model' },
        },
      },
    },
    isLoading: false,
    isError: false,
    isPending: false,
    isSuccess: true,
  })),
}));

describe('ConfigPanel', () => {
  beforeEach(() => {
    useCanvasEditStore.setState({
      workflowId: null, version: 0, nodes: [], edges: [],
      dirty: false, selectedNodeId: null,
    });
  });

  it('shows empty state when no node selected', () => {
    render(
      React.createElement(ReactFlowProvider, null,
        React.createElement(ConfigPanel)),
    );
    expect(screen.getByText('选中节点查看配置')).toBeDefined();
  });

  it('renders RJSF form when node is selected', () => {
    useCanvasEditStore.setState({
      nodes: [{ id: 'n1', type: 'llm', config: { model: 'gpt-4' }, position: { x: 0, y: 0 } }],
      selectedNodeId: 'n1',
    });
    render(
      React.createElement(ReactFlowProvider, null,
        React.createElement(ConfigPanel)),
    );
    // RJSF renders field labels; Model may appear multiple times in Ant Design
    expect(screen.getAllByText('Model').length).toBeGreaterThan(0);
  });
});
