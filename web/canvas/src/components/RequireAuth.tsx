import { Navigate, useLocation } from 'react-router-dom';
import { ReactNode } from 'react';
import { useAuthStore } from '@/store/useAuthStore';
import { isTokenExpired } from '@/lib/jwt';

export function RequireAuth({ children }: { children: ReactNode }) {
  const { token, clear } = useAuthStore();
  const location = useLocation();

  if (!token || isTokenExpired(token)) {
    if (token) clear();
    if (location.pathname === '/login') {
      return <>{children}</>;
    }
    return <Navigate to={`/login?redirect=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  }
  return <>{children}</>;
}
