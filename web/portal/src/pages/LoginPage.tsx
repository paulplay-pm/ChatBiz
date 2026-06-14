import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from 'ui/primitives/Button';
import { Input } from 'ui/primitives/Input';
import { Form } from 'ui/primitives/Form';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!username.trim()) return;
    localStorage.setItem('chatbiz.auth', JSON.stringify({ username, loginAt: Date.now() }));
    navigate('/');
  }

  // V4: SSO 企微扫码入口(dev mock) — 同窗口跳假 IM 页
  // 真实环境:异步调 ssoInitiate 拿 one-time token,这里 dev mode 直接 mock
  function ssoLogin() {
    const mockToken = `mock-${Date.now()}`;
    window.location.assign(`/portal/sso-mock-im?token=${mockToken}`);
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
        {/* V4: SSO 分隔线 + 扫码按钮 */}
        <div className="my-4 flex items-center gap-2 text-xs text-ink-400">
          <div className="flex-1 h-px bg-ink-200" />
          <span>或</span>
          <div className="flex-1 h-px bg-ink-200" />
        </div>
        <Button
          data-testid="sso-login-button"
          variant="secondary"
          className="w-full"
          onClick={ssoLogin}
        >
          🪪 企业扫码登录
        </Button>
      </div>
    </div>
  );
}
