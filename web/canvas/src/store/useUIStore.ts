import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  sidebarCollapsed: boolean;
  darkMode: boolean;
  currentWorkflowId: string | null;
  toggleSidebar: () => void;
  toggleDarkMode: () => void;
  setCurrentWorkflowId: (id: string | null) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      darkMode: false,
      currentWorkflowId: null,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      toggleDarkMode: () => set((s) => ({ darkMode: !s.darkMode })),
      setCurrentWorkflowId: (id) => set({ currentWorkflowId: id }),
    }),
    { name: 'chatbiz-ui' },
  ),
);
