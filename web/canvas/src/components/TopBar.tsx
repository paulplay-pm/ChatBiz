import { Layout, Avatar, Dropdown, Badge, Button } from 'antd';
import { UserOutlined, BellOutlined, MenuFoldOutlined, MenuUnfoldOutlined, LogoutOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/useAuthStore';
import { useUIStore } from '@/store/useUIStore';

export function TopBar() {
  const navigate = useNavigate();
  const { user, clear } = useAuthStore();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  return (
    <Layout.Header style={{ display: 'flex', alignItems: 'center', padding: '0 16px', background: '#fff', borderBottom: '1px solid #f0f0f0' }}>
      <Button type="text" icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} onClick={toggleSidebar} />
      <div style={{ fontSize: 20, fontWeight: 600, marginLeft: 12 }}>ChatBiz</div>
      <div style={{ flex: 1 }} />
      <Badge count={0} showZero={false}>
        <Button type="text" icon={<BellOutlined />} />
      </Badge>
      <Dropdown
        menu={{
          items: [
            { key: 'profile', label: `${user?.name} (${user?.id})`, disabled: true },
            { type: 'divider' },
            { key: 'logout', label: '登出', icon: <LogoutOutlined />, onClick: () => { clear(); navigate('/login'); } },
          ],
        }}
      >
        <Avatar icon={<UserOutlined />} style={{ marginLeft: 12, cursor: 'pointer', background: '#1890ff' }}>
          {user?.name?.[0]}
        </Avatar>
      </Dropdown>
    </Layout.Header>
  );
}
