import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { CreateWorkflowModal } from '@/components/CreateWorkflowModal';
import { DeleteConfirmModal } from '@/components/DeleteConfirmModal';
import { WorkflowCard } from '@/components/WorkflowCard';

vi.mock('@/lib/apiClient', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ data: { workflows: [], total: 0 } }),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(MemoryRouter, null, children));
};

describe('CreateWorkflowModal', () => {
  it('renders modal with form', () => {
    render(
      React.createElement(CreateWorkflowModal, { open: true, onClose: vi.fn() }),
      { wrapper },
    );
    expect(screen.getByText('新建工作流')).toBeDefined();
    expect(screen.getByText('名称')).toBeDefined();
  });
});

describe('DeleteConfirmModal', () => {
  it('renders modal when workflowId is set', () => {
    render(
      React.createElement(DeleteConfirmModal, { workflowId: 'w1', workflowName: 'test', onClose: vi.fn() }),
      { wrapper },
    );
    expect(screen.getByText('确认删除')).toBeDefined();
  });
});

describe('WorkflowCard', () => {
  it('renders workflow name and version', () => {
    const wf = {
      id: 'wf-1',
      version: 3,
      name: 'my flow',
      created_by: 'u-1',
      created_at: '2026-06-11T10:00:00',
      archived: false,
      definition_json: { mode: 'workflow', nodes: [], edges: [], variables: {} },
    };
    render(
      React.createElement(WorkflowCard, { workflow: wf, onDelete: vi.fn() }),
      { wrapper },
    );
    expect(screen.getByText('my flow')).toBeDefined();
  });
});
