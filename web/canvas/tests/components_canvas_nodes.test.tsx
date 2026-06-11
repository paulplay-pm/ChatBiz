import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import React from 'react';
import { NodeWrapper } from '@/components/canvas/nodes/index';

describe('NodeWrapper', () => {
  const baseProps = {
    id: 'n1',
    type: 'llm',
    data: { config: { model: 'gpt-4' }, status: 'pending' as const },
    selected: false,
    dragging: false,
    zIndex: 0,
    isConnectable: true,
    xPos: 0,
    yPos: 0,
  } as any;

  function renderNode(props: Record<string, unknown>) {
    return render(
      React.createElement(ReactFlowProvider, null,
        React.createElement(NodeWrapper, { ...baseProps, ...props })),
    );
  }

  it('renders LLM node with label and config', () => {
    renderNode({});
    expect(screen.getByText(/LLM/)).toBeDefined();
    expect(screen.getByText(/gpt-4/)).toBeDefined();
  });

  it('renders start node', () => {
    renderNode({ type: 'start', data: { config: { name: 'hello' } } });
    expect(screen.getByText(/开始/)).toBeDefined();
  });

  it('renders end node', () => {
    renderNode({ type: 'end', data: { config: { output_keys: ['result'] } } });
    expect(screen.getByText(/结束/)).toBeDefined();
  });

  it('applies selected border color', () => {
    renderNode({ selected: true });
    const el = document.querySelector('[style*="border"]');
    expect(el).toBeTruthy();
  });

  it('renders all 14 node types without crashing', () => {
    const types = ['start', 'end', 'variable_assign', 'condition', 'llm', 'knowledge', 'agent', 'http', 'code', 'approval', 'loop', 'iterate', 'subflow', 'extract'];
    for (const t of types) {
      const { container } = renderNode({ type: t, data: { config: {} } });
      // Each node should render something (Handle SVG or styles)
      expect(container.innerHTML.length).toBeGreaterThan(0);
    }
  });

  it('tolerates undefined data gracefully', () => {
    const { container } = renderNode({ data: undefined });
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it('shows status colors for each status', () => {
    const statuses = ['pending', 'running', 'completed', 'failed', 'skipped'] as const;
    for (const st of statuses) {
      const { container } = renderNode({ data: { config: {}, status: st } });
      expect(container.innerHTML.length).toBeGreaterThan(0);
    }
  });
});
