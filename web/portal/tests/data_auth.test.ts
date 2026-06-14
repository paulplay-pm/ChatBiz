import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ssoInitiate, ssoCallback, ssoMockImConfirm } from '@/data/auth';

describe('SSO auth helpers (V4 企微扫码 dev mock)', () => {
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
          qr_url: '/portal/sso-mock-im?token=abc123',
          one_time_token: 'abc123',
        }),
      });
      const r = await ssoInitiate();
      expect(r.qr_url).toContain('/portal/sso-mock-im?token=abc123');
      expect(r.one_time_token).toBe('abc123');
    });

    it('falls back to dev mock when fetch fails (nginx 没端点)', async () => {
      fetchMock.mockRejectedValueOnce(new Error('NetworkError'));
      const r = await ssoInitiate();
      expect(r.qr_url).toMatch(/\/portal\/sso-mock-im\?token=mock-/);
      expect(r.one_time_token).toMatch(/^mock-/);
    });

    it('falls back to dev mock on HTTP error', async () => {
      fetchMock.mockResolvedValueOnce({ ok: false, status: 404 });
      const r = await ssoInitiate();
      expect(r.qr_url).toMatch(/\/portal\/sso-mock-im/);
    });
  });

  describe('ssoCallback', () => {
    it('returns jwt + refresh + expires_in on 200', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jwt: 'jwt-xyz', refresh: 'ref-xyz', expires_in: 3600 }),
      });
      const r = await ssoCallback('one-time-tok');
      expect(r.jwt).toBe('jwt-xyz');
      expect(r.refresh).toBe('ref-xyz');
      expect(r.expires_in).toBe(3600);
    });

    it('falls back to dev mock JWT on fetch failure', async () => {
      fetchMock.mockRejectedValueOnce(new Error('NetworkError'));
      const r = await ssoCallback('one-time-tok');
      expect(r.jwt).toMatch(/^mock-jwt-one-time-tok-/);
      expect(r.refresh).toMatch(/^mock-refresh-one-time-tok$/);
      expect(r.expires_in).toBe(3600);
    });
  });

  describe('ssoMockImConfirm', () => {
    it('等价 ssoCallback:返回 jwt 等', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ jwt: 'jwt-confirm', refresh: 'ref-confirm', expires_in: 3600 }),
      });
      const r = await ssoMockImConfirm('confirm-tok');
      expect(r.jwt).toBe('jwt-confirm');
    });
  });
});
