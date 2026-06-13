import { Outlet } from 'react-router-dom';
import { TopBar } from './TopBar';
import { AppSidebar } from './Sidebar';
import { ErrorBoundary } from './ErrorBoundary';
import { ToastProvider } from 'ui/primitives/Toast';

export function AppLayout() {
  return (
    <ToastProvider>
      <div className="flex h-screen">
        <AppSidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-y-auto bg-ink-50 p-6">
            <ErrorBoundary>
              <Outlet />
            </ErrorBoundary>
          </main>
        </div>
      </div>
    </ToastProvider>
  );
}
