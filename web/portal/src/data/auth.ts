// V4: SSO 最小实现(企微扫码 dev mock)helpers
// - ssoInitiate(): 调 /api/auth/sso/wechat/initiate 拿 QR code URL
// - ssoCallback(token): 调 /api/auth/sso/wechat/callback 拿 JWT
// - ssoMockImConfirm(token): 在假 IM 页面调,confirm 后走 ssoCallback
//
// 全前端 mock:后端没有,fetch 走 nginx 5173 → 实际 nginx 没 /api/auth/sso/*,
// dev mode 用 try/catch fallback 到本地 mock

export interface SsoTokenResponse {
  jwt: string;
  refresh: string;
  expires_in: number;
}

export interface SsoInitiateResponse {
  qr_url: string;
  one_time_token: string;
}

const SSO_BASE = '/api/auth/sso';

async function safeJson<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as T;
}

export async function ssoInitiate(): Promise<SsoInitiateResponse> {
  try {
    const r = await fetch(`${SSO_BASE}/wechat/initiate`, { method: 'POST' });
    return await safeJson<SsoInitiateResponse>(r);
  } catch {
    // dev fallback: nginx 没这端点,直接造个 one-time token + 走 mock IM 路径
    const oneTimeToken = `mock-${Math.random().toString(36).slice(2, 10)}-${Date.now()}`;
    return {
      qr_url: `/portal/sso-mock-im?token=${oneTimeToken}`,
      one_time_token: oneTimeToken,
    };
  }
}

export async function ssoCallback(oneTimeToken: string): Promise<SsoTokenResponse> {
  try {
    const r = await fetch(`${SSO_BASE}/wechat/callback?token=${encodeURIComponent(oneTimeToken)}`);
    return await safeJson<SsoTokenResponse>(r);
  } catch {
    // dev fallback: 直接返 mock JWT
    return {
      jwt: `mock-jwt-${oneTimeToken}-${Date.now()}`,
      refresh: `mock-refresh-${oneTimeToken}`,
      expires_in: 3600,
    };
  }
}

export async function ssoMockImConfirm(oneTimeToken: string): Promise<SsoTokenResponse> {
  // 假 IM "确认登录" 按钮 → 等价 callback
  return ssoCallback(oneTimeToken);
}
