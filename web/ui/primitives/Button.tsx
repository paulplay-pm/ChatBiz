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

export function Button({ variant = 'primary', size = 'md', children, onClick, type = 'button', className = '', disabled = false, 'data-testid': testId = 'btn' }: {
  variant?: Variant; size?: Size; children: ReactNode; onClick?: () => void | Promise<void>; type?: 'button' | 'submit'; className?: string; disabled?: boolean; 'data-testid'?: string;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      className={`rounded-lg font-medium transition-all ${variants[variant]} ${sizes[size]} ${className} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {children}
    </button>
  );
}
