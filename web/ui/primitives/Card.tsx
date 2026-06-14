import { ReactNode } from 'react';
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div data-testid="card" className={`rounded-xl bg-white border border-ink-200 node-shadow p-4 ${className}`}>{children}</div>;
}
