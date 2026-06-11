import { describe, it, expect, vi } from 'vitest';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { render, screen } from '@testing-library/react';
import React from 'react';

// Suppress console.error from the caught error
vi.spyOn(console, 'error').mockImplementation(() => {});

// A component that throws on render
function Broken(): React.ReactElement {
  throw new Error('test crash');
}

describe('ErrorBoundary', () => {
  it('renders children when no error', () => {
    render(
      <ErrorBoundary><div>safe</div></ErrorBoundary>
    );
    expect(screen.getByText('safe')).toBeDefined();
  });

  it('renders fallback when child throws', () => {
    render(
      <ErrorBoundary><Broken /></ErrorBoundary>
    );
    expect(screen.getByText('出错了')).toBeDefined();
  });
});
