import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { RequireAuth } from '@/components/RequireAuth';

beforeEach(() => localStorage.clear());

describe('RequireAuth', () => {
  it('redirects to /login when no auth', () => {
    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div data-testid="login-page" />} />
          <Route element={<RequireAuth />}>
            <Route path="/protected" element={<div data-testid="protected" />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('login-page')).toBeInTheDocument();
    expect(screen.queryByTestId('protected')).toBeNull();
  });
  it('renders children when auth present', () => {
    localStorage.setItem('chatbiz.auth', JSON.stringify({ username: 'paul', loginAt: Date.now() }));
    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div data-testid="login-page" />} />
          <Route element={<RequireAuth><div data-testid="protected" /></RequireAuth>}>
            <Route path="/protected" element={null} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('protected')).toBeInTheDocument();
  });
});