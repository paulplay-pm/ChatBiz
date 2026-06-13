import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '@/components/primitives/Button';

describe('Button', () => {
  it('primary variant uses bg-brand-500', () => {
    render(<Button variant="primary">Click</Button>);
    expect(screen.getByTestId('btn').className).toMatch(/bg-brand-500/);
  });
  it('ghost variant uses bg-transparent', () => {
    render(<Button variant="ghost">Cancel</Button>);
    expect(screen.getByTestId('btn').className).toMatch(/bg-transparent/);
  });
  it('calls onClick when clicked', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    await userEvent.click(screen.getByTestId('btn'));
    expect(onClick).toHaveBeenCalledOnce();
  });
});