import { ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/useAuthStore';
import { isTokenExpired } from '@/lib/jwt';

/**
 * RequireAuth — canvas-specific wrapper around the shared web/ui RequireAuth.
 *
 * Reads the token from the zustand useAuthStore (canvas's source of truth) and
 * mirrors it to localStorage['chatbiz.auth'] so the shared `ui` RequireAuth
 * (which is used by nested routes / Outlet) can read it.
 *
 * T6 will replace this with a single source-of-truth (zustand writes localStorage
 * directly); until then this is the bridge that keeps both auth checks in sync.
 */
export function RequireAuth({ children }: { children?: ReactNode }) {
  const { token, clear } = useAuthStore();
  const location = useLocation();

  // Dev fallback: allow tokens prefixed with `dev:` to pass without expiry check.
  // (See openspec spec `canvas-auth` for the contract.)
  const isDevToken = token?.startsWith('dev:');

  if (!token || (!isDevToken && isTokenExpired(token))) {
    if (token) clear();
    if (location.pathname === '/login') {
      return <>{children ?? <Outlet />}</>;
    }
    return <Navigate to={`/login?redirect=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  }

  // Sync the canvas auth marker for any descendant `ui/primitives/RequireAuth`
  // and `<RequireAuth>` calls. In T6 useAuthStore will own this; until then we
  // write the marker every render so the shared primitive never blocks.
  if (typeof window !== 'undefined') {
    try {
      const existing = window.localStorage.getItem('chatbiz.auth');
      const desired = JSON.stringify({ token, ts: Date.now() });
      if (existing !== desired) {
        window.localStorage.setItem('chatbiz.auth', desired);
      }
    } catch {
      // localStorage unavailable (SSR / private mode); ignore — the zustand
      // check above is the authoritative gate for this build.
    }
  }

  return <>{children ?? <Outlet />}</>;
}
