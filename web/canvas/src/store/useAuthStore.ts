import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface User {
  id: string;
  name: string;
  email: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  clear: () => void;
}

// R4 fix: useAuthStore 同步写 localStorage['chatbiz.auth'] (跟 V1 portal
// 的 RequireAuth 契约对齐,web/ui/primitives/RequireAuth.tsx 默认读这个 key)。
// canvas-auth spec 没强制 localStorage 但 V1 portal 已用 'chatbiz.auth' 作为
// 跨 app 唯一 auth 标志,canvas 沿用以保持 RequireAuth 在两个 app 都 work。
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setAuth: (token, user) => set({ token, user }),
      clear: () => set({ token: null, user: null }),
    }),
    {
      name: 'chatbiz.auth',
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
