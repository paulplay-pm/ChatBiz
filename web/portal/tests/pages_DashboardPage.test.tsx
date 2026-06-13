import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from '@/pages/DashboardPage';

describe('DashboardPage', () => {
  it('renders 4 metric cards', () => {
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getAllByTestId('metric-card')).toHaveLength(4);
  });
  it('renders quick action button', () => {
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);
    expect(screen.getByTestId('quick-action')).toBeInTheDocument();
  });
});
