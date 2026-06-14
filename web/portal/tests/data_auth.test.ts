import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ssoInitiate, ssoCallback, ssoRefresh } from '@/data/auth';

describe('SSO auth helpers (V6a 真后端,无 dev mock)', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    global.fetch = fetchMock as any;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('ssoInitiate', () => {
    it('returns qr_url + one_time_token on 200', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          qr_url: 'https://open.weixin.qq.com/connect/oauth2/authorize?appid=...',
          one_time_token: 'ott-abc123',
        }),
      });
      const r = await ssoInitiate();
      expect(r.qr_url).toContain('open.weixin.qq.com');
      expect(r.one_time_token).toBe('ott-abc123');
    });

    it('throws on fetch network failure (no dev fallback)', async () => {
      fetchMock.mockRejectedValueOnce(new Error('NetworkError'));
      await expect(ssoInitiate()).rejects.toThrow(/NetworkError/);
    });

    it('throws on HTTP error with status code', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: false,
        status: 401,
        text: async () => 'Unauthorized',
      });
      await expect(ssoInitiate()).rejects.toThrow(/SSO 401/);
    });
  });

  describe('ssoCallback', () => {
    it('returns jwt + refresh + expires_in on 200', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jwt: 'jwt-xyz', refresh: 'ref-xyz', expires_in: 3600 }),
      });
      const r = await ssoCallback('code-abc', 'state-xyz');
      expect(r.jwt).toBe('jwt-xyz');
      expect(r.refresh).toBe('ref-xyz');
      expect(r.expires_in).toBe(3600);
    });

    it('throws on fetch network failure (no dev fallback)', async () => {
      fetchMock.mockRejectedValueOnce(new Error('NetworkError'));
      await expect(ssoCallback('code-abc', 'state-xyz')).rejects.toThrow(/NetworkError/);
    });
  });

  describe('ssoRefresh', () => {
    it('returns new jwt on 200', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jwt: 'jwt-new', refresh: 'ref-new', expires_in: 3600 }),
      });
      const r = await ssoRefresh('ref-old');
      expect(r.jwt).toBe('jwt-new');
      expect(r.refresh).toBe('ref-new');
    });
  });
});
