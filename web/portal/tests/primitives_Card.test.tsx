import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Card } from 'ui/primitives/Card';
import { MetricCard } from 'ui/primitives/MetricCard';
import { StatusDot } from 'ui/primitives/StatusDot';

describe('Card', () => {
  it('renders children', () => {
    render(<Card>hello</Card>);
    expect(screen.getByTestId('card')).toHaveTextContent('hello');
  });
});

describe('MetricCard', () => {
  it('renders label and value', () => {
    render(<MetricCard label="工作流" value={12} />);
    expect(screen.getByTestId('metric-card')).toHaveTextContent('工作流');
    expect(screen.getByTestId('metric-card')).toHaveTextContent('12');
  });
});

describe('StatusDot', () => {
  it('renders 5 status variants', () => {
    const { rerender } = render(<StatusDot status="running" />);
    expect(screen.getByTestId('status-dot').className).toMatch(/status-running/);
    rerender(<StatusDot status="success" />);
    expect(screen.getByTestId('status-dot').className).toMatch(/status-success/);
    rerender(<StatusDot status="error" />);
    expect(screen.getByTestId('status-dot').className).toMatch(/status-error/);
    rerender(<StatusDot status="idle" />);
    expect(screen.getByTestId('status-dot').className).toMatch(/status-idle/);
    rerender(<StatusDot status="pending" />);
    expect(screen.getByTestId('status-dot').className).toMatch(/status-pending/);
  });
});