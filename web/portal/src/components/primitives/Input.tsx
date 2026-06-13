import { ChangeEvent } from 'react';
export function Input({ value, onChange, placeholder, type = 'text', name }: {
  value?: string; onChange?: (e: ChangeEvent<HTMLInputElement>) => void; placeholder?: string; type?: string; name?: string;
}) {
  return (
    <input
      data-testid="input"
      name={name}
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className="w-full px-3 py-2 rounded-lg border border-ink-200 text-sm focus:outline-none focus:border-brand-500"
    />
  );
}