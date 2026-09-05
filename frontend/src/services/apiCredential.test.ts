/**
 * @vitest-environment jsdom
 *
 * Which credential wins, and why the answer is not "whichever is present".
 *
 * **This is a defect that shipped and was found by running the product.** Both
 * sources exist at once in the case nobody had exercised — the real
 * `electron/main.js` loading the Vite dev server — and they disagree:
 * `main.js` mints a fresh secret per launch and hands it over IPC, while Vite
 * baked in whatever `backend/api-secret` held when the dev server booted, a
 * file the backend stops writing once `ZARAM_API_SECRET` is set. The stale one
 * won, every request came back 401, and the interface said **"Zaram engine not
 * running"** about a backend that was up and answering the launcher's own
 * health check with 200.
 *
 * The rule is precedence, not presence: the bridge is authoritative because
 * the process on the other end is the one that minted the value.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

let originalFetch: typeof window.fetch;

beforeEach(() => {
  originalFetch = window.fetch;
});

afterEach(() => {
  window.fetch = originalFetch;
  delete (window as unknown as { zaram?: unknown }).zaram;
  vi.unstubAllEnvs();
  vi.resetModules();
});

/** Install a bridge reporting this launch's secret, as the preload does. */
function withBridge(secret: string | null) {
  (window as unknown as { zaram: unknown }).zaram = {
    app: { getApiSecret: () => Promise.resolve(secret) },
  };
}

/**
 * Install the wrapper, then report the credential it attaches to `url`.
 *
 * Asserting through a real `fetch` rather than reading the module's state: the
 * header is the thing the backend sees, and a credential resolved correctly
 * but attached to nothing would pass any test that stopped short of it.
 */
async function credentialSentTo(url: string): Promise<string | null> {
  let sent: string | null = null;

  // The spy goes on *before* the wrapper installs, so the wrapper wraps it.
  // Replacing `window.fetch` afterwards would discard the wrapper and measure
  // nothing — which it did, and every case came back null.
  window.fetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    sent = new Headers(init?.headers ?? {}).get('X-Zaram-Auth');
    return new Response('{}', { status: 200 });
  }) as typeof window.fetch;

  vi.resetModules();
  const { installApiCredential } = await import('./apiCredential');
  await installApiCredential();

  await window.fetch(url);
  return sent;
}

describe('installApiCredential', () => {
  it('prefers the desktop host over the value baked in at build time', async () => {
    // Both present and disagreeing — the exact case that shipped broken. The
    // build-time value stands in for a stale `backend/api-secret`.
    vi.stubEnv('VITE_ZARAM_API_SECRET', 'stale-from-the-file');
    withBridge('this-launch-from-the-host');

    expect(await credentialSentTo('/health')).toBe('this-launch-from-the-host');
  });

  it('falls back to the build-time value in a browser tab with no host', async () => {
    // No `window.zaram` at all — the case the Vite injection exists for.
    vi.stubEnv('VITE_ZARAM_API_SECRET', 'from-the-dev-server');

    expect(await credentialSentTo('/health')).toBe('from-the-dev-server');
  });

  it('falls back when the host is present but has no secret to give', async () => {
    vi.stubEnv('VITE_ZARAM_API_SECRET', 'from-the-dev-server');
    withBridge(null);

    expect(await credentialSentTo('/health')).toBe('from-the-dev-server');
  });

  it('never attaches the credential to another origin', async () => {
    // Rule 3 committed by a convenience: a local credential sent to a third
    // party. The wrapper is global, so this is the guard that matters most.
    withBridge('this-launch-from-the-host');

    expect(await credentialSentTo('https://example.com/collect')).toBeNull();
  });
});
