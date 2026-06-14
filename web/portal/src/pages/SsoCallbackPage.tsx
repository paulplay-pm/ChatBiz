import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Button } from 'ui/primitives/Button';
import { ssoCallback } from '@/data/auth';

// V6a: 企微扫码回调页 — 企微服务器 redirect 跳回 ?code=&state=
// 调真后端 /api/auth/sso/wechat/callback 拿 JWT,写 localStorage,跳首页
export default function SsoCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const code = params.get('code') ?? '';
  const state = params.get('state') ?? '';
  const [exchanging, setExchanging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!code || !state) {
      setError('缺少 code 或 state 参数');
    }
  }, [code, state]);

  async function handleExchange() {
    setExchanging(true);
    try {
      const { jwt, refresh, expires_in } = await ssoCallback(code, state);
      // 写 localStorage auth state(对齐 portal username/password 登录模式)
      localStorage.setItem(
        'chatbiz.auth',
        JSON.stringify({
          username: 'sso-user',
          loginAt: Date.now(),
          via: 'sso-wechat-scan',
          jwt,
          refresh,
          expiresIn: expires_in,
        }),
      );
      // 关弹窗(若在 popup)或跳首页
      if (window.opener) {
        window.opener.postMessage({ type: 'sso-success' }, window.location.origin);
        window.close();
      } else {
        navigate('/');
      }
    } catch (e) {
      setError((e as Error).message);
      setExchanging(false);
    }
  }

  return (
    <div data-testid="sso-callback-page" className="min-h-screen flex items-center justify-center bg-ink-50">
      <div className="w-[480px] rounded-2xl bg-white p-8 node-shadow">
        <h1 className="text-xl font-semibold text-ink-900 mb-2">企业微信扫码登录</h1>
        <p className="text-sm text-ink-500 mb-4">V6a 企微回调 — 交换 code 拿 JWT</p>
        <div className="rounded-lg bg-ink-50 p-4 mb-4 space-y-2">
          <div>
            <div className="text-xs text-ink-500 mb-1">code</div>
            <div data-testid="sso-code" className="text-sm text-ink-900 font-mono break-all">
              {code}
            </div>
          </div>
          <div>
            <div className="text-xs text-ink-500 mb-1">state</div>
            <div data-testid="sso-state" className="text-sm text-ink-900 font-mono break-all">
              {state}
            </div>
          </div>
        </div>
        {error && (
          <div className="text-sm text-red-600 mb-4" data-testid="sso-error">
            {error}
          </div>
        )}
        <Button
          data-testid="sso-exchange"
          className="w-full"
          onClick={handleExchange}
          disabled={exchanging || !code || !state}
        >
          {exchanging ? '交换中...' : '完成登录'}
        </Button>
      </div>
    </div>
  );
}
