import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ComingSoonPage from '@/pages/ComingSoonPage';

describe('ComingSoonPage', () => {
  it('renders menu name from ?from= query', () => {
    render(<MemoryRouter initialEntries={['/coming-soon?from=credential']}><ComingSoonPage /></MemoryRouter>);
    expect(screen.getByText(/凭证/)).toBeInTheDocument();
  });
  it('renders default message when unknown from', () => {
    render(<MemoryRouter initialEntries={['/coming-soon?from=foo']}><ComingSoonPage /></MemoryRouter>);
    expect(screen.getByText(/此功能/)).toBeInTheDocument();
  });
  it('renders default message when no from', () => {
    render(<MemoryRouter initialEntries={['/coming-soon']}><ComingSoonPage /></MemoryRouter>);
    expect(screen.getByText(/此功能/)).toBeInTheDocument();
  });
});
