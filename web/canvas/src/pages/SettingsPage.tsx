import { Card, Form, Switch, Select } from 'antd';
import { useUIStore } from '@/store/useUIStore';
import { useAuthStore } from '@/store/useAuthStore';

export default function SettingsPage() {
  const { darkMode, toggleDarkMode } = useUIStore();
  const user = useAuthStore((s) => s.user);

  return (
    <div style={{ maxWidth: 600 }}>
      <Card title="个人设置" style={{ marginBottom: 16 }}>
        <Form layout="vertical">
          <Form.Item label="用户 ID">
            <span>{user?.id}</span>
          </Form.Item>
          <Form.Item label="用户名">
            <span>{user?.name}</span>
          </Form.Item>
          <Form.Item label="邮箱">
            <span>{user?.email}</span>
          </Form.Item>
        </Form>
      </Card>

      <Card title="界面设置">
        <Form layout="vertical">
          <Form.Item label="暗色主题">
            <Switch checked={darkMode} onChange={toggleDarkMode} />
          </Form.Item>
          <Form.Item label="默认节点图标样式">
            <Select defaultValue="emoji" style={{ width: 200 }}>
              <Select.Option value="emoji">Emoji(默认)</Select.Option>
              <Select.Option value="outline">线性图标</Select.Option>
              <Select.Option value="filled">填充图标</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
