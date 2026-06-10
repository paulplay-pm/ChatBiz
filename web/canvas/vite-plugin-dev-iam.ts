import type { Plugin } from 'vite';
import { createHmac } from 'node:crypto';

// Lightweight HS256 JWT signer for the dev IAM mock.
// In production, this entire plugin should be disabled.
function signDevJwt(payload: Record<string, unknown>, secret: string): string {
  const header = { alg: 'HS256', typ: 'JWT' };
  const enc = (obj: object) => Buffer.from(JSON.stringify(obj)).toString('base64url');
  const h = enc(header);
  const p = enc(payload);
  const sig = createHmac('sha256', secret).update(`${h}.${p}`).digest('base64url');
  return `${h}.${p}.${sig}`;
}

export function devIam(): Plugin {
  const SECRET = 'dev-iam-secret-do-not-use-in-prod';
  return {
    name: 'chatbiz-dev-iam',
    configureServer(server) {
      server.middlewares.use('/api/auth/login', (req, res, next) => {
        if (req.method !== 'POST') return next();
        let body = '';
        req.on('data', (c) => { body += c; });
        req.on('end', () => {
          try {
            const { username, password } = JSON.parse(body);
            if (!username) {
              res.statusCode = 400;
              res.setHeader('Content-Type', 'application/json');
              res.end(JSON.stringify({ error_class: 'user', error_message: 'username 必填' }));
              return;
            }
            // Accept any non-empty password in dev mode
            const now = Math.floor(Date.now() / 1000);
            const token = signDevJwt(
              { sub: `u-${username}`, name: username, email: `${username}@chatbiz`, iat: now, exp: now + 8 * 3600 },
              SECRET,
            );
            res.statusCode = 200;
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({
              token,
              user: { id: `u-${username}`, name: username, email: `${username}@chatbiz` },
            }));
          } catch (e) {
            res.statusCode = 500;
            res.setHeader('Content-Type', 'application/json');
            res.end(JSON.stringify({ error_class: 'internal', error_message: String(e) }));
          }
        });
      });
    },
  };
}
