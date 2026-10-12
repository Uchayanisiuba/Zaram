/**
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { frontendOf, openStartedApp, type StartedCall } from './openStartedApp';
import { useBrowserStore } from '@/stores/browserStore';

const call = (over: Partial<StartedCall> = {}): StartedCall => ({
  server: 'code',
  tool: 'start_app_stack',
  verdict: 'allow',
  appUrl: 'http://127.0.0.1:5173',
  ...over,
});

const instant = { sleep: async () => undefined };

function withPane(present: boolean) {
  (window as unknown as { zaram?: unknown }).zaram = present ? { browser: {} } : {};
}

beforeEach(() => {
  withPane(true);
  useBrowserStore.setState({ open: false, pendingUrl: null });
});

afterEach(() => {
  delete (window as unknown as { zaram?: unknown }).zaram;
});

describe('opening an app that was just started', () => {
  it('opens the pane at the frontend address once the server answers', async () => {
    const answers = vi.fn(async () => true);
    expect(await openStartedApp(call(), { answers, ...instant })).toBe(true);
    expect(useBrowserStore.getState().open).toBe(true);
    expect(useBrowserStore.getState().pendingUrl).toBe('http://127.0.0.1:5173');
  });

  it('does the same for a single app', async () => {
    const answers = async () => true;
    expect(await openStartedApp(call({ tool: 'start_app', appUrl: 'http://localhost:3000/' }), { answers, ...instant })).toBe(true);
    expect(useBrowserStore.getState().pendingUrl).toBe('http://localhost:3000/');
  });

  it('waits until the server answers rather than opening on a refused connection', async () => {
    let tries = 0;
    const answers = vi.fn(async () => ++tries >= 4);
    const opening = openStartedApp(call(), { answers, ...instant });
    expect(useBrowserStore.getState().open).toBe(false);
    expect(await opening).toBe(true);
    expect(answers).toHaveBeenCalledTimes(4);
    expect(useBrowserStore.getState().open).toBe(true);
  });

  it('gives up quietly when nothing ever answers', async () => {
    const answers = vi.fn(async () => false);
    expect(await openStartedApp(call(), { answers, ...instant, waitMs: 2000 })).toBe(false);
    expect(useBrowserStore.getState().open).toBe(false);
  });

  it('opens once when the same start is announced twice', async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => (release = resolve));
    const answers = vi.fn(async () => {
      await gate;
      return true;
    });
    const show = vi.spyOn(useBrowserStore.getState(), 'show');
    const first = openStartedApp(call(), { answers, ...instant });
    const second = openStartedApp(call(), { answers, ...instant });
    release();
    expect([await first, await second]).toEqual([true, false]);
    expect(show).toHaveBeenCalledTimes(1);
  });
});

describe('the page of a stack', () => {
  const p = (url: string | null, role?: string | null, running = true) => ({ url, role, running });

  it('is the process that says it is the frontend, whatever order they came in', () => {
    expect(frontendOf([p('http://127.0.0.1:8000', 'backend'), p('http://127.0.0.1:5173', 'frontend')])).toBe(
      'http://127.0.0.1:5173',
    );
  });

  it('is the only process when there is only one', () => {
    expect(frontendOf([p('http://127.0.0.1:8000', 'backend')])).toBe('http://127.0.0.1:8000');
  });

  it('is the one process not known to be something else', () => {
    expect(frontendOf([p('http://127.0.0.1:8000', 'backend'), p('http://127.0.0.1:5173', null)])).toBe(
      'http://127.0.0.1:5173',
    );
  });

  it('is nothing, not a guess, when several answer and none says which', () => {
    expect(frontendOf([p('http://127.0.0.1:3001'), p('http://127.0.0.1:3002')])).toBe('');
  });

  it('ignores a process that has stopped or has no address yet', () => {
    expect(frontendOf([p('http://127.0.0.1:5173', 'frontend', false), p(null, 'backend')])).toBe('');
    expect(frontendOf(undefined)).toBe('');
  });
});

describe('what it never opens', () => {
  const never = async (c: StartedCall) => {
    const answers = vi.fn(async () => true);
    expect(await openStartedApp(c, { answers, ...instant })).toBe(false);
    expect(answers).not.toHaveBeenCalled();
    expect(useBrowserStore.getState().open).toBe(false);
  };

  it('a remote address', () => never(call({ appUrl: 'https://example.com/' })));
  it('a LAN address, which DNS or routing could point anywhere', () => never(call({ appUrl: 'http://192.168.1.5:3000' })));
  it('an address with credentials in it', () => never(call({ appUrl: 'http://user:pw@localhost:3000' })));
  it('a call that has no address yet', () => never(call({ appUrl: '' })));
  it('a call the gate did not allow', () => never(call({ verdict: 'confirm' })));
  it('a tool that only reports on an app', () => never(call({ tool: 'get_app_status' })));
  it('a driving tool, which is already at the page', () => never(call({ tool: 'open_in_browser' })));
  it("another server's tool of the same name", () => never(call({ server: 'somebody-elses' })));
  it('anything without a pane to open it in', async () => {
    withPane(false);
    await never(call());
  });
});
