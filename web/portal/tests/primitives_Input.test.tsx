import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Input } from '@/components/primitives/Input';

describe('Input', () => {
  it('renders with placeholder', () => {
    render(<Input placeholder="username" />);
    expect(screen.getByPlaceholderText('username')).toBeInTheDocument();
  });
  it('updates value on type', async () => {
    const onChange = vi.fn();
    render(<Input placeholder="username" onChange={onChange} />);
    await userEvent.type(screen.getByPlaceholderText('username'), 'paul');
    expect(onChange).toHaveBeenCalled();
  });
});