// Global setup for Vitest integration tests.
//
// Polls http://localhost:5173/healthz (the test compose nginx proxy to mcp)
// until it returns 200, with a 60-second budget. Fails the whole run with
// process.exit(1) if the stack isn't ready.

const HEALTH_URL = 'http://localhost:5173/healthz';
const TIMEOUT_MS = 60_000;
const INTERVAL_MS = 1_000;

export default async function globalSetup(): Promise<void> {
  const deadline = Date.now() + TIMEOUT_MS;
  let lastErr: unknown;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(HEALTH_URL, { method: 'GET' });
      if (res.ok) {
        return;
      }
      lastErr = new Error(`healthz status ${res.status}`);
    } catch (e) {
      lastErr = e;
    }
    await new Promise((r) => setTimeout(r, INTERVAL_MS));
  }
  throw new Error(
    `Test compose stack not ready at ${HEALTH_URL} within ${TIMEOUT_MS}ms. ` +
      `Run 'make test-integration up' first. Last error: ${String(lastErr)}`,
  );
}
