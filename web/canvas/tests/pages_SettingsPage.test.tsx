import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import SettingsPage from '@/pages/SettingsPage';

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient();
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(MemoryRouter, null, children));
};

describe('SettingsPage', () => {
  it('renders settings page title', () => {
    render(<SettingsPage />, { wrapper });
    expect(screen.getByText('个人设置')).toBeDefined();
    expect(screen.getByText('界面设置')).toBeDefined();
  });
});
