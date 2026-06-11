import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { RequireAuth } from '@/components/RequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

function makeToken(exp: number): string {
  const payload = Buffer.from(JSON.stringify({ sub: 'u-1', exp })).toString('base64url');
  return `header.${payload}.sig`;
}

function renderWithinRoutes(initialEntries: string[], element: React.ReactElement) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/login" element={<div>login page</div>} />
        <Route path="*" element={element} />
      </Routes>
    </MemoryRouter>
  );
}

describe('RequireAuth', () => {
  afterEach(() => {
    cleanup();
    // Reset store to prevent cross-test contamination
    useAuthStore.getState().clear();
  });

  it('renders children when token is valid (future exp)', () => {
    const futureExp = Math.floor(Date.now() / 1000) + 3600;
    useAuthStore.setState({ token: makeToken(futureExp), user: { id: 'u-1', name: 'A', email: 'a@c' } });
    renderWithinRoutes(['/workflows'], <RequireAuth><div data-testid="valid-child">ok</div></RequireAuth>);
    expect(screen.queryByTestId('valid-child')).toBeTruthy();
  });

  it('redirects when token is null', () => {
    useAuthStore.getState().clear();
    renderWithinRoutes(['/workflows'], <RequireAuth><div data-testid="no-token-child">secret</div></RequireAuth>);
    // Navigate redirects to /login; children not rendered
    expect(screen.queryByText('login page')).toBeTruthy();
    expect(screen.queryByTestId('no-token-child')).toBeNull();
  });

  it('redirects when token is expired', () => {
    const pastExp = Math.floor(Date.now() / 1000) - 3600;
    useAuthStore.setState({ token: makeToken(pastExp), user: { id: 'u-1', name: 'A', email: 'a@c' } });
    renderWithinRoutes(['/workflows'], <RequireAuth><div data-testid="expired-child">top secret</div></RequireAuth>);
    expect(screen.queryByText('login page')).toBeTruthy();
    expect(screen.queryByTestId('expired-child')).toBeNull();
  });
});
