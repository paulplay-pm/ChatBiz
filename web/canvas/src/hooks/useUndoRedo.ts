import { useCanvasEditStore } from '@/store/useCanvasEditStore';
import { useEffect } from 'react';

export function useUndoRedo() {
  const store = useCanvasEditStore.temporal;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isMod = e.metaKey || e.ctrlKey;
      if (!isMod) return;
      if (e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        store.getState().undo();
      } else if ((e.key === 'z' && e.shiftKey) || e.key === 'y') {
        e.preventDefault();
        store.getState().redo();
      } else if (e.key === 's') {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent('chatbiz-save-workflow'));
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [store]);
}
