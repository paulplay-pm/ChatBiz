import { ReactNode, MouseEventHandler } from 'react';
type CardProps = {
  children: ReactNode;
  className?: string;
  onClick?: MouseEventHandler<HTMLDivElement>;
};
export function Card({ children, className = '', onClick }: CardProps) {
  return (
    <div
      data-testid="card"
      className={`rounded-xl bg-white border border-ink-200 node-shadow p-4 ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
}
