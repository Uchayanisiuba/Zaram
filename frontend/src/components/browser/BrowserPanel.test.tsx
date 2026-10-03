/**
 * @vitest-environment jsdom
 *
 * The chrome around the hole.
 *
 * The page itself is a `BrowserView` in the main process and is not in this
 * tree at all, so what is testable here is exactly what this component is
 * responsible for: the tab strip, the address bar, the rectangle it reports,
 * and what it says when the policy refuses something.
 *
 * The class that matters most is `WhatItSaysWhenRefused`. Each reason is a
 * different thing to tell somebody — "browsing is off" has a fix, "that is
 * not an address" has a different one — and collapsing them into one
 * sentence is how a control that is working reads as broken.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const fetchLocalServers = vi.fn();

vi.mock('@/services/localServersClient', () => ({
  fetchLocalServers: () => fetchLocalServers(),
}));

import BrowserPanel from './BrowserPanel';

function tab(over: Record<string, unknown> = {}) {
  return { id: 't1', url: '', title: 'New tab', active: true, ...over };
}

/** The main-process bridge, as the preload exposes it. */
function bridge(over: Record<string, unknown> = {}) {
  let listener: ((p: unknown) => void) | null = null;
  const api = {
    open: vi.fn(async () => 't2'),
    select: vi.fn(async () => {}),
    navigate: vi.fn(async () => ({ ok: true, allow: true, url: 'https://example.com/' })),
    close: vi.fn(async () => {}),
    setBounds: vi.fn(async () => {}),
    act: vi.fn(async () => {}),
    show: vi.fn(async () => {}),
    hide: vi.fn(async () => {}),
    state: vi.fn(async () => ({ tabs: [tab()], activeId: 't1' })),
    onTabs: vi.fn((fn: (p: unknown) => void) => {
      listener = fn;
      return () => {};
    }),
    ...over,
  };
  return { api, push: (payload: unknown) => listener && act(() => listener!(payload)) };
}

beforeEach(() => {
  fetchLocalServers.mockReset().mockResolvedValue({ servers: [], hidden: 0 });
  // jsdom has no ResizeObserver, and the panel uses one to keep the view in
  // step with the hole through resizes React does not re-render for.
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    observe() {}
    disconnect() {}
  };
});

afterEach(() => {
  cleanup();
  delete (window as { zaram?: unknown }).zaram;
  vi.restoreAllMocks();
});

const user = () => userEvent.setup();

async function open(over: Record<string, unknown> = {}) {
  const b = bridge(over);
  (window as { zaram?: unknown }).zaram = { browser: b.api };
  render(<BrowserPanel />);
  await waitFor(() => expect(b.api.state).toHaveBeenCalled());
  return b;
}

describe('without a desktop host', () => {
  it('says so rather than drawing chrome around a hole nothing will fill', async () => {
    render(<BrowserPanel />);
    expect(screen.getByText(/needs the desktop app/i)).toBeTruthy();
    expect(screen.queryByTestId('address-bar')).toBeNull();
  });
});

describe('the tabs', () => {
  it('opens one when there are none', async () => {
    const b = await open({ state: vi.fn(async () => ({ tabs: [], activeId: null })) });
    await waitFor(() => expect(b.api.open).toHaveBeenCalled());
  });

  it('shows what main pushes', async () => {
    const b = await open();
    b.push({ tabs: [tab({ id: 't1', title: 'Wikipedia', url: 'https://en.wikipedia.org/' })], activeId: 't1' });
    expect(screen.getByTestId('tab-t1').textContent).toBe('Wikipedia');
  });

  it('a new tab is asked for, not invented locally', async () => {
    // Main owns the view, so it owns the id. A renderer that minted one
    // would be a second place deciding what a tab is.
    const b = await open();
    await user().click(screen.getByTestId('new-tab'));
    expect(b.api.open).toHaveBeenCalled();
  });

  it('closes the one that was asked for', async () => {
    const b = await open();
    b.push({ tabs: [tab({ id: 't1' }), tab({ id: 't2', active: false })], activeId: 't1' });
    await user().click(screen.getByTestId('close-t2'));
    expect(b.api.close).toHaveBeenCalledWith('t2');
  });
});

describe('leaving the pane', () => {
  it('takes the view off the window without closing the tabs', async () => {
    // A BrowserView is painted *above* this window. Unmounting the React
    // tree leaves it sitting over whichever surface the person went to --
    // which looks like the browser having eaten Memory.
    const b = await open();
    cleanup();
    expect(b.api.hide).toHaveBeenCalled();
    expect(b.api.close).not.toHaveBeenCalled();
  });
});

describe('the new tab page', () => {
  it('hides the view, because the page under it is React', async () => {
    const b = await open();
    await waitFor(() => expect(b.api.hide).toHaveBeenCalled());
  });

  it('lists what is running', async () => {
    fetchLocalServers.mockResolvedValue({
      servers: [
        { port: 5173, url: 'http://127.0.0.1:5173', name: 'Ride Share', pid: 1, process: 'node.exe', origin: 'project', projectId: 'ride-share', webbish: true },
      ],
      hidden: 0,
    });
    await open();
    await waitFor(() => expect(screen.getByTestId('server-5173')).toBeTruthy());
    expect(screen.getByText('Ride Share')).toBeTruthy();
  });

  it('collapses the machine\u2019s other processes behind a count', async () => {
    // Measured on the maintainer's machine: 46 listening, 44 of them
    // Discord, OneDrive and svchost. Listing those is a port scan.
    fetchLocalServers.mockResolvedValue({
      servers: [
        { port: 8420, url: 'http://127.0.0.1:8420', name: 'Zaram', pid: 1, process: 'python.exe', origin: 'zaram', projectId: '', webbish: true },
        { port: 6463, url: 'http://127.0.0.1:6463', name: 'Discord', pid: 2, process: 'Discord.exe', origin: 'other', projectId: '', webbish: false },
      ],
      hidden: 1,
    });
    await open();
    await waitFor(() => expect(screen.getByTestId('server-8420')).toBeTruthy());
    expect(screen.queryByTestId('server-6463')).toBeNull();

    await user().click(screen.getByTestId('show-other-servers'));
    expect(screen.getByTestId('server-6463')).toBeTruthy();
  });

  it('opening one navigates the current tab', async () => {
    fetchLocalServers.mockResolvedValue({
      servers: [
        { port: 5173, url: 'http://127.0.0.1:5173', name: 'Ride Share', pid: 1, process: 'node.exe', origin: 'project', projectId: 'r', webbish: true },
      ],
      hidden: 0,
    });
    const b = await open();
    await waitFor(() => expect(screen.getByTestId('server-5173')).toBeTruthy());
    await user().click(screen.getByTestId('server-5173'));
    expect(b.api.navigate).toHaveBeenCalledWith('t1', 'http://127.0.0.1:5173');
  });

  it('tells an empty machine apart from an unreadable one honestly', async () => {
    await open();
    await waitFor(() =>
      expect(screen.getByText(/Nothing is listening|could not be read/i)).toBeTruthy(),
    );
  });
});

describe('the address bar', () => {
  it('sends what was typed', async () => {
    const b = await open();
    await user().type(screen.getByTestId('address-bar'), 'example.com{Enter}');
    expect(b.api.navigate).toHaveBeenCalledWith('t1', 'example.com');
  });

  it('does not normalise the address itself', async () => {
    // The policy decides what a URL is, and it has 42 tests. A second
    // opinion here could disagree with the one that actually navigates.
    const b = await open();
    await user().type(screen.getByTestId('address-bar'), 'localhost:3000{Enter}');
    expect(b.api.navigate).toHaveBeenCalledWith('t1', 'localhost:3000');
  });

  it('follows the page when it changes', async () => {
    const b = await open();
    b.push({ tabs: [tab({ url: 'https://example.com/a' })], activeId: 't1' });
    await waitFor(() =>
      expect((screen.getByTestId('address-bar') as HTMLInputElement).value).toBe(
        'https://example.com/a',
      ),
    );
  });
});

describe('what it says when refused', () => {
  it('names the fix when browsing is off', async () => {
    await open({
      navigate: vi.fn(async () => ({ ok: true, allow: false, reason: 'browse-not-allowed' })),
    });
    await user().type(screen.getByTestId('address-bar'), 'example.com{Enter}');
    await waitFor(() => expect(screen.getByTestId('browser-refusal').textContent).toMatch(/Settings/i));
  });

  it('says a phrase is not an address, and why it will not search', async () => {
    // Searching it would contact a host the person never named.
    await open({
      navigate: vi.fn(async () => ({ ok: false, allow: false, reason: 'not-an-address' })),
    });
    await user().type(screen.getByTestId('address-bar'), 'what is a tomato{Enter}');
    await waitFor(() =>
      expect(screen.getByTestId('browser-refusal').textContent).toMatch(/not an address/i),
    );
  });

  it('a refused scheme gets its own sentence', async () => {
    await open({
      navigate: vi.fn(async () => ({ ok: false, allow: false, reason: 'scheme' })),
    });
    await user().type(screen.getByTestId('address-bar'), 'file:///C:/{Enter}');
    await waitFor(() =>
      expect(screen.getByTestId('browser-refusal').textContent).toMatch(/http and https/i),
    );
  });

  it('a link main stopped is reported, since it never passed through navigate', async () => {
    const b = await open();
    // Wait for the first tab to settle before pushing. The refusal is
    // cleared whenever the active tab changes -- which is right, navigating
    // away should clear it -- and `state()` resolving counts as a change.
    await waitFor(() => expect(screen.getByTestId('tab-t1')).toBeTruthy());
    b.push({ refused: { tabId: 't1', url: 'https://example.com/' } });
    await waitFor(() => expect(screen.getByTestId('browser-refusal')).toBeTruthy());
  });

  it('clears once something opens', async () => {
    const b = await open({
      navigate: vi.fn(async () => ({ ok: true, allow: false, reason: 'browse-not-allowed' })),
    });
    await user().type(screen.getByTestId('address-bar'), 'example.com{Enter}');
    await waitFor(() => expect(screen.getByTestId('browser-refusal')).toBeTruthy());
    b.push({ tabs: [tab({ url: 'http://127.0.0.1:5173/' })], activeId: 't1' });
    await waitFor(() => expect(screen.queryByTestId('browser-refusal')).toBeNull());
  });
});

describe('the rectangle', () => {
  it('is reported so main knows where to paint', async () => {
    const b = await open();
    b.push({ tabs: [tab({ url: 'https://example.com/' })], activeId: 't1' });
    await waitFor(() => expect(b.api.setBounds).toHaveBeenCalled());
    const bounds = (b.api.setBounds.mock.calls[0] as unknown[])[0] as Record<string, number>;
    for (const key of ['x', 'y', 'width', 'height']) expect(key in bounds).toBe(true);
  });
});
