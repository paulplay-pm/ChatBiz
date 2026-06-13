import { ReactNode } from 'react';
export function Modal({ open, onClose, children, title }: { open: boolean; onClose: () => void; children: ReactNode; title: string }) {
  if (!open) return null;
  return (
    <div data-testid="modal-backdrop" onClick={onClose} className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center">
      <div data-testid="modal" onClick={(e) => e.stopPropagation()} className="bg-white rounded-xl p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold text-ink-900 mb-4">{title}</h3>
        {children}
      </div>
    </div>
  );
}
