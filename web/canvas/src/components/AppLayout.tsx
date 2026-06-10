import { Layout } from 'antd';
import { Outlet } from 'react-router-dom';
import { TopBar } from './TopBar';
import { Sidebar } from './Sidebar';
import { ErrorBoundary } from './ErrorBoundary';

export function AppLayout() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <TopBar />
      <Layout>
        <Sidebar />
        <Layout.Content style={{ padding: 24, background: '#f0f2f5' }}>
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
