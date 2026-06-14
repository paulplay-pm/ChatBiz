import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from 'ui/primitives/Button';
import { Input } from 'ui/primitives/Input';
import { Form } from 'ui/primitives/Form';
import { ssoInitiate } from '@/data/auth';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [ssoLoading, setSsoLoading] = useState(false);
  const [ssoError, setSsoError] = useState<string | null>(null);
  const navigate = useNavigate();

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!username.trim()) return;
    localStorage.setItem('chatbiz.auth', JSON.stringify({ username, loginAt: Date.now() }));
    navigate('/');
  }

  // V6a: SSO 企微扫码入口 — 调真后端 /api/auth/sso/wechat/initiate
  // 拿 qr_url 跳到企微服务器扫码,企微 redirect 回 /sso-callback
  async function ssoLogin() {
    setSsoLoading(true);
    setSsoError(null);
    try {
      const { qr_url } = await ssoInitiate();
      window.location.assign(qr_url);
    } catch (e) {
      setSsoError((e as Error).message);
      setSsoLoading(false);
    }
  }

  return (
    <div data-testid="login-page" className="min-h-screen flex items-center justify-center bg-ink-50">
      <div className="w-96 rounded-2xl bg-white p-8 node-shadow">
        <h1 className="text-2xl font-semibold text-ink-900 mb-2">ChatBiz Portal</h1>
        <p className="text-sm text-ink-500 mb-6">企业 AI Agent 平台</p>
        <Form onSubmit={submit}>
          <Input placeholder="username" name="username" value={username} onChange={(e) => setUsername(e.target.value)} />
          <Input placeholder="password" name="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <Button type="submit">登 录</Button>
        </Form>
        {/* V6a: SSO 分隔线 + 扫码按钮 */}
        <div className="my-4 flex items-center gap-2 text-xs text-ink-400">
          <div className="flex-1 h-px bg-ink-200" />
          <span>或</span>
          <div className="flex-1 h-px bg-ink-200" />
        </div>
        {ssoError && (
          <div className="text-sm text-red-600 mb-2" data-testid="sso-login-error">
            {ssoError}
          </div>
        )}
        <Button
          data-testid="sso-login-button"
          variant="secondary"
          className="w-full"
          onClick={ssoLogin}
          disabled={ssoLoading}
        >
          {ssoLoading ? '正在跳转企微...' : '🪪 企业扫码登录'}
        </Button>
      </div>
    </div>
  );
}
