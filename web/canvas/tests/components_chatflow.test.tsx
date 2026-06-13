import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { ChatBubble } from '@/components/chatflow/ChatBubble';

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient();
  return React.createElement(QueryClientProvider, { client: qc },
    React.createElement(MemoryRouter, null, children));
};

describe('ChatBubble', () => {
  it('renders user message', () => {
    render(<ChatBubble type="user" content="hello" />, { wrapper });
    expect(screen.getByText('hello')).toBeDefined();
  });

  it('renders AI message', () => {
    render(<ChatBubble type="ai" content="response" />, { wrapper });
    expect(screen.getByText('response')).toBeDefined();
  });

  it('renders tool message with header', () => {
    render(<ChatBubble type="tool" content="called fetch" />, { wrapper });
    expect(screen.getByText('🔧 工具调用')).toBeDefined();
  });

  it('renders approval message with header', () => {
    render(<ChatBubble type="approval" content="waiting" />, { wrapper });
    expect(screen.getByText('✋ 人工审批')).toBeDefined();
  });
});
