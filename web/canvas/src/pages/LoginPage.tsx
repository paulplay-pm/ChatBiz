import { useState } from 'react';
import { Form, Input, Button } from 'ui/index';
import { useToast } from 'ui/primitives/Toast';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '@/lib/apiClient';
import { useAuthStore } from '@/store/useAuthStore';

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const setAuth = useAuthStore((s) => s.setAuth);
  const toast = useToast();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const form = e.currentTarget as HTMLFormElement;
    const fd = new FormData(form);
    const username = String(fd.get('username') ?? '');
    const password = String(fd.get('password') ?? '');
    setLoading(true);
    try {
      const r = await api.post('/api/auth/login', { username, password });
      setAuth(r.data.token, r.data.user);
      toast.info(`欢迎,${r.data.user.name}`);
      const redirect = params.get('redirect') || '/workflows';
      navigate(redirect, { replace: true });
    } catch (err: unknown) {
      const e2 = err as { response?: { data?: { error_message?: string } } };
      toast.error(e2.response?.data?.error_message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-ink-50">
      <div className="bg-white rounded-xl p-8 w-96 node-shadow border border-ink-200">
        <h1 className="text-2xl font-semibold text-ink-900 mb-6">ChatBiz 登录</h1>
        <Form onSubmit={onSubmit}>
          <div>
            <label className="block text-sm font-medium text-ink-700 mb-1">用户名</label>
            <Input name="username" placeholder="任意非空 username(dev mode)" />
          </div>
          <div className="mt-4">
            <label className="block text-sm font-medium text-ink-700 mb-1">密码</label>
            <Input
              name="password"
              type="password"
              placeholder="任意密码(dev mode)"
            />
          </div>
          <span>
            <Button variant="primary" type="submit">
              {loading ? '登录中…' : '登录'}
            </Button>
          </span>
        </Form>
      </div>
    </div>
  );
}
