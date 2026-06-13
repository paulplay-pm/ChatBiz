import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '@/pages/LoginPage';

beforeEach(() => {
  localStorage.clear();
});

describe('LoginPage', () => {
  it('writes chatbiz.auth to localStorage on submit', async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    await user.type(screen.getByPlaceholderText('username'), 'paul');
    await user.type(screen.getByPlaceholderText('password'), 'dev');
    await user.click(screen.getByTestId('btn'));
    const stored = JSON.parse(localStorage.getItem('chatbiz.auth')!);
    expect(stored.username).toBe('paul');
    expect(stored.loginAt).toBeGreaterThan(0);
  });
});
