import { ReactNode } from 'react';
import { Navigate, Outlet } from 'react-router-dom';

export function RequireAuth({ children }: { children?: ReactNode }) {
  const auth = localStorage.getItem('chatbiz.auth');
  if (!auth) return <Navigate to="/login" replace />;
  return <>{children ?? <Outlet />}</>;
}