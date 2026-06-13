import { FormEvent, ReactNode } from 'react';
export function Form({ onSubmit, children }: { onSubmit: (e: FormEvent) => void; children: ReactNode }) {
  return <form data-testid="form" onSubmit={onSubmit} className="space-y-4">{children}</form>;
}