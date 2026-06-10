import { useState } from 'react';
import { Form, Input, Button, Card, message } from 'antd';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '@/lib/apiClient';
import { useAuthStore } from '@/store/useAuthStore';

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const setAuth = useAuthStore((s) => s.setAuth);

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const r = await api.post('/api/auth/login', values);
      setAuth(r.data.token, r.data.user);
      message.success(`欢迎,${r.data.user.name}`);
      const redirect = params.get('redirect') || '/workflows';
      navigate(redirect, { replace: true });
    } catch (e: any) {
      message.error(e.response?.data?.error_message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f0f2f5' }}>
      <Card title="ChatBiz 登录" style={{ width: 360 }}>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item label="用户名" name="username" rules={[{ required: true, message: '用户名必填' }]}>
            <Input placeholder="任意非空 username(dev mode)" autoFocus />
          </Form.Item>
          <Form.Item label="密码" name="password">
            <Input.Password placeholder="任意密码(dev mode)" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}
