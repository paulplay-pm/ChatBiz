import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import { TopBar } from '@/components/TopBar';
import { Sidebar } from '@/components/Sidebar';

describe('TopBar', () => {
  it('renders the ChatBiz brand', () => {
    render(
      <MemoryRouter>
        <TopBar />
      </MemoryRouter>
    );
    // ChatBiz as heading text
    const h = screen.getByText('ChatBiz');
    expect(h).toBeDefined();
  });
});

describe('Sidebar', () => {
  it('renders navigation items', () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );
    expect(screen.getByText('工作流')).toBeDefined();
  });
});

describe('AppLayout', () => {
  it('renders layout structure', () => {
    render(
      <MemoryRouter>
        <TopBar />
        <Sidebar />
      </MemoryRouter>
    );
    // TopBar has ChatBiz
    expect(screen.getAllByText('ChatBiz').length).toBeGreaterThanOrEqual(1);
    // Sidebar has 工作流
    expect(screen.getAllByText('工作流').length).toBeGreaterThanOrEqual(1);
  });
});
