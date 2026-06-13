import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AppLayout } from '@/components/AppLayout';
import { MENU, SECTIONS } from '@/data/menu';

describe('AppLayout', () => {
  it('renders Sidebar + Header + Outlet', () => {
    render(
      <MemoryRouter initialEntries={['/x']}>
        <Routes>
          <Route element={<AppLayout menuItems={MENU} sections={SECTIONS} activeId="dashboard" />}>
            <Route path="/x" element={<div data-testid="outlet-content">hello</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    expect(screen.getByTestId('header')).toBeInTheDocument();
    expect(screen.getByTestId('outlet-content')).toHaveTextContent('hello');
  });
});
