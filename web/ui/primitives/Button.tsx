import { ReactNode } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost';
type Size = 'sm' | 'md' | 'lg';
const variants: Record<Variant, string> = {
  primary: 'bg-brand-500 hover:bg-brand-600 text-white',
  secondary: 'bg-ink-100 hover:bg-ink-200 text-ink-900',
  ghost: 'bg-transparent hover:bg-ink-100 text-ink-700',
};
const sizes: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-base',
};

export function Button({ variant = 'primary', size = 'md', children, onClick, type = 'button' }: {
  variant?: Variant; size?: Size; children: ReactNode; onClick?: () => void; type?: 'button' | 'submit';
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      data-testid="btn"
      className={`rounded-lg font-medium transition-all ${variants[variant]} ${sizes[size]}`}
    >
      {children}
    </button>
  );
}
