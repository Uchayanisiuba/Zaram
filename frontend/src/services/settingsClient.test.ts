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
  fetchRoutingSettings,
  fetchImageSetting,
  setImageLocality,
  setImageModel,
  updateRoutingSettings,
  fetchModelServers,
  startModelServer,
  updateModelServer,
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
      // The policy that replaced the typed number, 4 October 2026. This
      // assertion is exact on purpose and that is why it caught them.
      context_policy: null,
      context_override: null,
      overflow_policy: null,
      max_reply_tokens: null,
      // The other fields behind the same endpoint, and the same rule: a client
      // setting the preference must not clear somebody's per-task assignments
      // or their routing model as a side effect of not mentioning them.
      task_models: null,
      router_model: null,
      // Thinking on/off (E2b, 20 September 2026) sits behind the same
      // endpoint and gets the same null.
      thinking: null,
      // null means leave it alone, like every other field here: a
      // client changing the routing preference must not clear somebody’s
      // context window as a side effect.
    });
  });

  it('sends an empty string to hand the choice back to Zaram', async () => {
    fetchMock.mockResolvedValue(json({ routing_preference: 'auto', default_model: null }));

    await updateRoutingSettings({ defaultModel: '' });

    expect(lastCall().body).toMatchObject({ default_model: '' });
  });

  it('sends only the task slot that changed', async () => {
    // The backend merges slot by slot, so a screen setting the coding model
    // must not have to resend the vision one and risk clobbering it.
    fetchMock.mockResolvedValue(
      json({ routing_preference: 'auto', task_models: { code: 'coder' } }),
    );

    await updateRoutingSettings({ taskModels: { code: 'coder' } });

    expect(lastCall().body).toMatchObject({ task_models: { code: 'coder' } });
  });

  it('reads the slots back, and a save does not blank them', async () => {
    // The POST answers with the same payload the GET does. Without that, a
    // client replacing its state with the response would lose its list of
    // slots the moment somebody used one — a control that disappears when you
    // touch it.
    fetchMock.mockResolvedValue(
      json({
        routing_preference: 'auto',
        task_models: { vision: 'seer' },
        task_slots: ['code', 'vision'],
      }),
    );

    const after = await updateRoutingSettings({ taskModels: { vision: 'seer' } });

    expect(after.taskSlots).toEqual(['code', 'vision']);
    expect(after.taskModels).toEqual({ vision: 'seer' });
  });

  it('drops a stored value that is not a usable model name', async () => {
    // The settings file is a file, and a person can edit it. A value that is
    // not a string has no business reaching a picker as a selected option.
    fetchMock.mockResolvedValue(
      json({ routing_preference: 'auto', task_models: { code: 17, vision: '' } }),
    );

    expect((await fetchRoutingSettings()).taskModels).toEqual({});
  });
});

describe('where pictures are drawn first', () => {
  it('reads the preference and who can draw, and never invents a drawer', async () => {
    fetchMock.mockResolvedValue(
      json({
        prefer: 'cloud',
        local_ok: false,
        cloud: [{ id: 'nvidia_nim', name: 'flux-schnell · NVIDIA NIM', ok: false, reason: 'no key', remedy: 'add one' }],
        answers: null,
      }),
    );
    const setting = await fetchImageSetting();
    expect(setting.prefer).toBe('cloud');
    expect(setting.localOk).toBe(false);
    expect(setting.cloud[0]).toMatchObject({ id: 'nvidia_nim', ok: false, remedy: 'add one' });
    expect(setting.answers).toBeNull();
  });

  it('sends the choice as the one field the backend reads', async () => {
    fetchMock.mockResolvedValue(json({ prefer: 'local', local_ok: true, cloud: [], answers: 'flux-schnell' }));
    const setting = await setImageLocality('local');
    expect(lastCall().url).toContain('/images/setting');
    expect(lastCall().body).toEqual({ prefer: 'local' });
    expect(setting.answers).toBe('flux-schnell');
  });
});

/**
 * **What is installed, including what is not being used.**
 *
 * Reported 29 September 2026: *"I installed Qwen Image as a replacement, seems
 * like it didn't replace."* It had not. Discovery took the first usable folder
 * in sorted order, `flux1-schnell-nf4` sorts before `qwen-image`, and every
 * surface in the product agreed to say nothing about it.
 *
 * So the transport carries the unusable ones too. A list of only what works
 * would have been exactly as silent as the bug.
 */
describe('what is in the image model folder', () => {
  it('carries the models that cannot be used, with their reason', async () => {
    fetchMock.mockResolvedValue(
      json({
        prefer: 'local',
        local_ok: true,
        local: {
          drawing_with: 'flux1-schnell-nf4',
          chosen: null,
          installed: [
            { name: 'flux1-schnell-nf4', pipeline: 'FluxPipeline', usable: true, why_not: '' },
            {
              name: 'qwen-image',
              pipeline: 'QwenImagePipeline',
              usable: false,
              why_not: 'QwenImagePipeline — Zaram draws locally with FLUX only',
            },
          ],
        },
        cloud: [],
        answers: 'flux1-schnell-nf4',
      }),
    );

    const setting = await fetchImageSetting();
    expect(setting.local.drawingWith).toBe('flux1-schnell-nf4');
    expect(setting.local.chosen).toBeNull();
    expect(setting.local.installed).toHaveLength(2);
    expect(setting.local.installed[1]).toMatchObject({
      name: 'qwen-image',
      usable: false,
    });
    expect(setting.local.installed[1].whyNot).toContain('FLUX');
  });

  it('reports nothing rather than claiming nothing is installed, on an older backend', async () => {
    // `local` absent means the backend never spoke, which is not the same as
    // "no models". Rendering it as a claim would be inventing a value — the
    // thing `CLAUDE.md` forbids on a status surface.
    fetchMock.mockResolvedValue(json({ prefer: 'local', local_ok: true, cloud: [], answers: null }));
    const setting = await fetchImageSetting();
    expect(setting.local.installed).toEqual([]);
    expect(setting.local.drawingWith).toBeNull();
  });

  it('sends the pick as the one field, and can clear it back to the first', async () => {
    // A fresh Response per call: a body reads once, so reusing one object
    // fails the second assertion for a reason that has nothing to do with
    // what is being tested.
    const body = { prefer: 'local', local_ok: true, cloud: [], answers: 'qwen-image' };
    fetchMock.mockImplementation(async () => json(body));

    await setImageModel('qwen-image');
    expect(lastCall().url).toContain('/images/setting');
    expect(lastCall().body).toEqual({ model: 'qwen-image' });

    // The empty string is meaningful: "whichever is first". Omitting the field
    // cannot say that, which is why the backend reads `''` rather than null.
    await setImageModel('');
    expect(lastCall().body).toEqual({ model: '' });
  });
});

describe('the model servers', () => {
  const row = (over: Record<string, unknown> = {}) => ({
    id: 'tabbyapi', label: 'TabbyAPI', port: 1234, state: 'running', installed: true,
    path: 'C:\tabby', model_count: 1, models: ['Big-27B'], can_start: false,
    problem: '', auto_start: true, fields: ['path', 'python'], failure: '', log_path: '',
    zaram_sees: 1, ...over,
  });

  it('reads what the backend reports', async () => {
    fetchMock.mockResolvedValue(json([row()]));
    const [server] = await fetchModelServers();
    expect(server).toMatchObject({
      id: 'tabbyapi', state: 'running', modelCount: 1, models: ['Big-27B'],
      autoStart: true, zaramSees: 1, fields: ['path', 'python'],
    });
    expect(lastCall().url).toBe('/providers/model-servers');
  });

  it('treats a state it does not know as unknown, not as running', async () => {
    /** A newer backend may add a state. Drawing it as `running` would be a green
     *  tick for something Zaram does not understand. */
    fetchMock.mockResolvedValue(json([row({ state: 'quantum' })]));
    expect((await fetchModelServers())[0].state).toBe('unknown');
  });

  it('keeps "not asked" apart from "none"', async () => {
    /** `null` is *not asked*; zero is *Zaram holds none of them*. Collapsing them
     *  would either hide the gap this exists to show or invent one. */
    fetchMock.mockResolvedValue(json([row({ zaram_sees: null }), row({ zaram_sees: 0 })]));
    const [notAsked, none] = await fetchModelServers();
    expect(notAsked.zaramSees).toBeNull();
    expect(none.zaramSees).toBe(0);
  });

  it('reads auto-start as on unless it is exactly false', async () => {
    fetchMock.mockResolvedValue(json([row({ auto_start: undefined }), row({ auto_start: false })]));
    const [absent, off] = await fetchModelServers();
    expect(absent.autoStart).toBe(true);
    expect(off.autoStart).toBe(false);
  });

  it('survives a backend that sends nothing it recognises', async () => {
    fetchMock.mockResolvedValue(json({ not: 'a list' }));
    expect(await fetchModelServers()).toEqual([]);
  });

  it('starts a server with a POST, and encodes the id into the path', async () => {
    fetchMock.mockResolvedValue(json(row({ state: 'starting' })));
    const server = await startModelServer('tabby api/../x');
    expect(lastCall().init.method).toBe('POST');
    expect(lastCall().url).toBe('/providers/model-servers/tabby%20api%2F..%2Fx/start');
    expect(server.state).toBe('starting');
  });

  it('carries the backend sentence when a start is refused', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'Something other than TabbyAPI is already using port 1234.' }, 409));
    await expect(startModelServer('tabbyapi')).rejects.toMatchObject({
      status: 409, message: 'Something other than TabbyAPI is already using port 1234.',
    });
  });

  it('sends only what was changed', async () => {
    fetchMock.mockResolvedValue(json(row({ auto_start: false })));
    await updateModelServer('tabbyapi', { autoStart: false });
    expect(lastCall().init.method).toBe('PUT');
    expect(lastCall().body).toEqual({ auto_start: false });
  });

  it('sends an empty string to clear a field, which is not the same as omitting it', async () => {
    /** Omitting leaves it alone; `""` clears it. Dropping empty strings on the way
     *  out would make it impossible to say *go back to looking*. */
    fetchMock.mockResolvedValue(json(row()));
    await updateModelServer('tabbyapi', { path: '' });
    expect(lastCall().body).toEqual({ path: '' });
  });

  it('is refused with the reason when the location is not an install', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'That folder does not look like a TabbyAPI checkout.' }, 400));
    await expect(updateModelServer('tabbyapi', { path: 'C:\nope' })).rejects.toBeInstanceOf(SettingsError);
  });
});
