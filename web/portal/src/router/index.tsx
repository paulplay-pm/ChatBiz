import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AppLayout } from '@/components/AppLayout';
import { RequireAuth } from 'ui/primitives/RequireAuth';
import LoginPage from '@/pages/LoginPage';
import SsoCallbackPage from '@/pages/SsoCallbackPage';
import DashboardPage from '@/pages/DashboardPage';
import ComingSoonPage from '@/pages/ComingSoonPage';
import { MENU, SECTIONS } from '@/data/menu';

function useActiveId() {
  const loc = useLocation();
  return MENU.find((m) => loc.pathname.startsWith(m.href.split('?')[0] ?? ''))?.id || 'dashboard';
}

function AppLayoutWrapper() {
  const activeId = useActiveId();
  return <AppLayout menuItems={MENU} sections={SECTIONS} activeId={activeId} />;
}

export function PortalRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      {/* V6a: SSO 企微回调页 — 不需要 auth,在 RequireAuth 外面 */}
      <Route path="/sso-callback" element={<SsoCallbackPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppLayoutWrapper />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/coming-soon" element={<ComingSoonPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
