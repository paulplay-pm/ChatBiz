import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Button } from 'ui/primitives/Button';
import { ssoMockImConfirm } from '@/data/auth';

// V4: 假 IM 弹窗页面 — 模拟企业微信扫码确认登录
// 真实环境:用户用企业微信扫描 QR code → 企微服务器回调
// V4 dev mock:页面渲染"模拟企微扫码" UI + 确认按钮
export default function SsoMockImPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') ?? '';
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError('缺少 token 参数');
    }
  }, [token]);

  async function handleConfirm() {
    setConfirming(true);
    try {
      const { jwt, refresh, expires_in } = await ssoMockImConfirm(token);
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
      setConfirming(false);
    }
  }

  return (
    <div data-testid="sso-mock-im-page" className="min-h-screen flex items-center justify-center bg-ink-50">
      <div className="w-[480px] rounded-2xl bg-white p-8 node-shadow">
        <h1 className="text-xl font-semibold text-ink-900 mb-2">企业微信扫码登录</h1>
        <p className="text-sm text-ink-500 mb-4">V4 dev mock — 模拟企微扫码确认</p>
        <div className="rounded-lg bg-ink-50 p-4 mb-4">
          <div className="text-xs text-ink-500 mb-1">one-time token</div>
          <div data-testid="sso-token" className="text-sm text-ink-900 font-mono break-all">
            {token}
          </div>
        </div>
        {error && (
          <div className="text-sm text-red-600 mb-4" data-testid="sso-error">
            {error}
          </div>
        )}
        <Button
          data-testid="sso-confirm"
          className="w-full"
          onClick={handleConfirm}
          disabled={confirming || !token}
        >
          {confirming ? '确认中...' : '确认登录'}
        </Button>
      </div>
    </div>
  );
}
