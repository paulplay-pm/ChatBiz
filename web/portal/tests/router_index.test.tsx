import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PortalRouter } from '@/router';

beforeEach(() => {
  localStorage.clear();
});

describe('PortalRouter', () => {
  it('unauthenticated /login route renders LoginPage', () => {
    render(<MemoryRouter initialEntries={['/login']}><PortalRouter /></MemoryRouter>);
    expect(screen.getByTestId('login-page')).toBeInTheDocument();
  });
  it('unauthenticated / redirects to /login', () => {
    render(<MemoryRouter initialEntries={['/']}><PortalRouter /></MemoryRouter>);
    expect(screen.getByTestId('login-page')).toBeInTheDocument();
  });
  it('authenticated / renders Dashboard inside AppLayout', () => {
    localStorage.setItem('chatbiz.auth', JSON.stringify({ username: 'paul', loginAt: Date.now() }));
    render(<MemoryRouter initialEntries={['/']}><PortalRouter /></MemoryRouter>);
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
  });
  it('authenticated /coming-soon renders ComingSoonPage', () => {
    localStorage.setItem('chatbiz.auth', JSON.stringify({ username: 'paul', loginAt: Date.now() }));
    render(<MemoryRouter initialEntries={['/coming-soon?from=credential']}><PortalRouter /></MemoryRouter>);
    expect(screen.getByTestId('coming-soon')).toBeInTheDocument();
  });
  it('authenticated unknown route redirects to /', () => {
    localStorage.setItem('chatbiz.auth', JSON.stringify({ username: 'paul', loginAt: Date.now() }));
    render(<MemoryRouter initialEntries={['/garbage']}><PortalRouter /></MemoryRouter>);
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
  });
});
