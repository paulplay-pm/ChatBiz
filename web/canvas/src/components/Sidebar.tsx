import { Layout, Menu } from 'antd';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppstoreOutlined, NodeIndexOutlined, DatabaseOutlined, ApiOutlined, SettingOutlined,
} from '@ant-design/icons';
import { useUIStore } from '@/store/useUIStore';

const items = [
  { key: '/workflows', icon: <NodeIndexOutlined />, label: '工作流' },
  { key: '/chatflow', icon: <AppstoreOutlined />, label: '对话' },
  { key: '/knowledge', icon: <DatabaseOutlined />, label: '知识库' },
  { key: '/plugins', icon: <ApiOutlined />, label: '插件' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
];

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { sidebarCollapsed } = useUIStore();

  return (
    <Layout.Sider
      width={220}
      collapsed={sidebarCollapsed}
      collapsedWidth={64}
      style={{ background: '#001529' }}
      breakpoint="md"
    >
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[items.find((i) => location.pathname.startsWith(i.key))?.key || '/workflows']}
        items={items}
        onClick={({ key }) => navigate(key)}
        style={{ marginTop: 16 }}
      />
    </Layout.Sider>
  );
}
