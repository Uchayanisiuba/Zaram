/**
 * What the settings transport must never get wrong.
 *
 * Three of these are security properties rather than behaviour, and they are
 * the reason this file exists: each one is invisible in review once the code
 * around it grows, and each fails silently rather than loudly.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import {
  SettingsError,
  connectCloudProvider,
  disconnectCloudProvider,
  fetchCloudStatus,
  fetchProviderCatalogue,
  setKillSwitch,
  updateRoutingSettings,
} from './settingsClient';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** The request the code under test made, parsed. */
const lastCall = () => {
  // Indexed rather than `.at(-1)`: this project's `lib` target predates it, and
  // widening the whole project's TypeScript lib to satisfy one test assertion
  // is a change to what the product may compile against, decided by a test.
  const calls = fetchMock.mock.calls;
  const [url, init] = calls[calls.length - 1] as [string, RequestInit | undefined];
  return {
    url,
    init: init ?? {},
    headers: (init?.headers ?? {}) as Record<string, string>,
    body: init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null,
  };
};

describe('a key travels one way', () => {
  it('sends the key when connecting', async () => {
    fetchMock.mockResolvedValue(json({ connections: [], configured: false, generated: '2026-08-12' }));

    await connectCloudProvider({ providerId: 'openai', apiKey: 'sk-test-abcd1234' });

    expect(lastCall().body).toMatchObject({ provider_id: 'openai', api_key: 'sk-test-abcd1234' });
  });

  it('never surfaces a whole key from a response', async () => {
    // The backend reduces a key to four characters before it is served. If a
    // future version starts returning more, this is where it is noticed: the
    // parsed connection has a `keyTail` and no field that could hold a key.
    fetchMock.mockResolvedValue(
      json({
        configured: true,
        generated: '2026-08-12',
        connections: [
          {
            provider_id: 'openai',
            display_name: 'OpenAI',
            base_url: 'https://api.openai.com/v1',
            key_tail: '1234',
            locality: 'cloud',
          },
        ],
      }),
    );

    const status = await fetchCloudStatus();
    const connection = status.connections[0];

    expect(connection.keyTail).toBe('1234');
    expect(JSON.stringify(connection)).not.toContain('sk-');
    expect(Object.keys(connection)).not.toContain('apiKey');
  });
});

describe('mutating calls force a CORS preflight', () => {
  // Without a non-safelisted header the browser sends these as *simple*
  // requests, which CORS does not prevent — it only stops the response being
  // read, and an attacker repointing Zaram's cloud endpoint does not need to
  // read anything.
  it.each([
    ['connect', () => connectCloudProvider({ providerId: 'openai', apiKey: 'k' })],
    ['disconnect', () => disconnectCloudProvider('openai')],
    ['kill switch', () => setKillSwitch(true)],
    ['routing', () => updateRoutingSettings({ routingPreference: 'auto' })],
  ])('%s sends X-Zaram-Client', async (_name, call) => {
    fetchMock.mockResolvedValue(json({ connections: [], on: true, routing_preference: 'auto' }));

    await call();

    expect(lastCall().headers['X-Zaram-Client']).toBeTruthy();
  });

  it('does not send it on a plain read', async () => {
    fetchMock.mockResolvedValue(json({ generated: '2026-08-12', providers: [] }));

    await fetchProviderCatalogue();

    expect(lastCall().headers['X-Zaram-Client']).toBeUndefined();
  });
});

describe('a refusal keeps the backend’s own sentence', () => {
  it('surfaces detail rather than a generic failure', async () => {
    // These sentences are written for a person to act on — the catalogue's
    // reason for why Claude cannot be called yet is more use than "400".
    const detail =
      'Zaram cannot call Claude directly yet — it uses a different request format from the one Zaram speaks.';
    fetchMock.mockResolvedValue(json({ detail }, 400));

    await expect(connectCloudProvider({ providerId: 'anthropic', apiKey: 'k' })).rejects.toThrow(
      detail,
    );
  });

  it('carries the status code for a caller that needs it', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'nope' }, 403));

    await expect(setKillSwitch(true)).rejects.toMatchObject({
      name: 'SettingsError',
      status: 403,
    });
  });

  it('falls back to the status when the body is not JSON', async () => {
    // The realistic cause is the dev proxy answering with index.html, which is
    // a 200 — but a non-JSON error body must not produce "undefined" either.
    fetchMock.mockResolvedValue(new Response('<!doctype html>', { status: 502 }));

    await expect(setKillSwitch(true)).rejects.toBeInstanceOf(SettingsError);
  });
});

describe('routing updates leave untouched fields alone', () => {
  it('sends null for a field that was not supplied', async () => {
    // Both fields live behind one endpoint, so a client setting the preference
    // must not clear the chosen model as a side effect.
    fetchMock.mockResolvedValue(json({ routing_preference: 'prefer_local', default_model: 'x' }));

    await updateRoutingSettings({ routingPreference: 'prefer_local' });

    expect(lastCall().body).toEqual({
      routing_preference: 'prefer_local',
      default_model: null,
    });
  });

  it('sends an empty string to hand the choice back to Zaram', async () => {
    fetchMock.mockResolvedValue(json({ routing_preference: 'auto', default_model: null }));

    await updateRoutingSettings({ defaultModel: '' });

    expect(lastCall().body).toMatchObject({ default_model: '' });
  });
});
