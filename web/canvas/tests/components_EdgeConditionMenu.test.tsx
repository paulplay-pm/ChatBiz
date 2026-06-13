import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { EdgeConditionMenu } from '@/components/canvas/EdgeConditionMenu';
import { ToastProvider } from 'ui/primitives/Toast';

describe('EdgeConditionMenu', () => {
  it('renders modal with title', () => {
    render(
      React.createElement(ToastProvider, null,
        React.createElement(EdgeConditionMenu, {
          open: true,
          initialValue: '{{ n1.output.score }} > 0.8',
          onClose: vi.fn(),
          onSave: vi.fn(),
        })),
    );
    expect(screen.getByText('设置边条件')).toBeDefined();
  });

  it('renders textarea with initial value', () => {
    render(
      React.createElement(ToastProvider, null,
        React.createElement(EdgeConditionMenu, {
          open: true,
          initialValue: '{{ n1.output.score }} > 0.8',
          onClose: vi.fn(),
          onSave: vi.fn(),
        })),
    );
    // Modal TextArea uses Ant Design; verify the value is present
    const allValues = screen.getAllByDisplayValue(/n1.output/);
    expect(allValues.length).toBeGreaterThan(0);
  });
});
