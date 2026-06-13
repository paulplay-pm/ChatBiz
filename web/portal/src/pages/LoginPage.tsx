import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/primitives/Button';
import { Input } from '@/components/primitives/Input';
import { Form } from '@/components/primitives/Form';

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
      </div>
    </div>
  );
}
