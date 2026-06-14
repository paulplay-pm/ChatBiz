// V6a: SSO helpers 调真后端(V4 dev mock 已移除)
// - ssoInitiate(): 调 /api/auth/sso/wechat/initiate 拿 QR code URL
// - ssoCallback(code, state): 企微跳回后调 /api/auth/sso/wechat/callback 拿 JWT
// - ssoRefresh(refresh): 调 /api/auth/sso/refresh 拿新 JWT
//
// 全部走真 fetch + 错误抛错(后端 401/5xx 由调用方 toast 处理)

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
  if (!res.ok) {
    const errText = await res.text().catch(() => '');
    throw new Error(`SSO ${res.status}${errText ? `: ${errText}` : ''}`);
  }
  return (await res.json()) as T;
}

export async function ssoInitiate(): Promise<SsoInitiateResponse> {
  const r = await fetch(`${SSO_BASE}/wechat/initiate`, { method: 'POST' });
  return await safeJson<SsoInitiateResponse>(r);
}

export async function ssoCallback(code: string, state: string): Promise<SsoTokenResponse> {
  const r = await fetch(
    `${SSO_BASE}/wechat/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
  );
  return await safeJson<SsoTokenResponse>(r);
}

export async function ssoRefresh(refresh: string): Promise<SsoTokenResponse> {
  const r = await fetch(`${SSO_BASE}/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  });
  return await safeJson<SsoTokenResponse>(r);
}
