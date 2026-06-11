import { describe, it, expect, beforeEach } from 'vitest';
import { useUIStore } from '@/store/useUIStore';

describe('useUIStore', () => {
  beforeEach(() => {
    // Reset to initial state
    useUIStore.setState({
      sidebarCollapsed: false,
      darkMode: false,
      currentWorkflowId: null,
    });
  });

  it('initial state defaults', () => {
    const s = useUIStore.getState();
    expect(s.sidebarCollapsed).toBe(false);
    expect(s.darkMode).toBe(false);
    expect(s.currentWorkflowId).toBeNull();
  });

  it('toggleSidebar flips collapsed', () => {
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarCollapsed).toBe(true);
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
  });

  it('toggleDarkMode flips dark mode', () => {
    useUIStore.getState().toggleDarkMode();
    expect(useUIStore.getState().darkMode).toBe(true);
    useUIStore.getState().toggleDarkMode();
    expect(useUIStore.getState().darkMode).toBe(false);
  });

  it('setCurrentWorkflowId sets id', () => {
    useUIStore.getState().setCurrentWorkflowId('wf-1');
    expect(useUIStore.getState().currentWorkflowId).toBe('wf-1');
    useUIStore.getState().setCurrentWorkflowId(null);
    expect(useUIStore.getState().currentWorkflowId).toBeNull();
  });
});
