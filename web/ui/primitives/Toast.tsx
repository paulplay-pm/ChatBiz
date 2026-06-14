import { createContext, ReactNode, useCallback, useContext, useState } from 'react';

type ToastKind = 'security' | 'user' | 'info';
type ToastItem = { id: number; kind: ToastKind; message: string };
type Ctx = { push: (kind: ToastKind, message: string) => void };

const ToastContext = createContext<Ctx | null>(null);
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return {
    error: (msg: string) => ctx.push('security', msg),
    warn: (msg: string) => ctx.push('user', msg),
    info: (msg: string) => ctx.push('info', msg),
  };
}

const colorMap: Record<ToastKind, string> = {
  security: 'bg-red-500',
  user: 'bg-yellow-500',
  info: 'bg-brand-500',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((kind: ToastKind, message: string) => {
    const id = Date.now() + Math.random();
    setItems((prev) => [...prev, { id, kind, message }]);
    setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 5000);
  }, []);
  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div data-testid="toast-host" className="fixed top-4 left-1/2 -translate-x-1/2 z-[9999] flex flex-col gap-2">
        {items.map((t) => (
          <div key={t.id} data-testid={`toast-${t.kind}`} className={`${colorMap[t.kind]} text-white px-4 py-2 rounded-lg shadow-lg`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
