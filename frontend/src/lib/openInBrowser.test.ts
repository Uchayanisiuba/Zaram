import { afterEach, describe, expect, it, vi } from 'vitest';

import { isWebAddress, isLocalAppAddress, onOpen, openInBrowser, openAppAddress } from './openInBrowser';
import { useBrowserStore } from '@/stores/browserStore';

/** The packaged app denies window-open (`hardenWindow`), so every external
 *  link has to go through the shell bridge; these pin that route. */
describe('openInBrowser', () => {
  afterEach(() => {
    delete (window as unknown as { zaram?: unknown }).zaram;
  });

  it('uses the shell bridge when the desktop host provides one', () => {
    const openExternal = vi.fn();
    (window as unknown as { zaram?: unknown }).zaram = { shell: { openExternal } };
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    openInBrowser('https://example.com/key');
    expect(openExternal).toHaveBeenCalledWith('https://example.com/key');
    expect(open).not.toHaveBeenCalled();
    open.mockRestore();
  });

  it('falls back to a noopener tab in a plain browser', () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    openInBrowser('https://example.com');
    expect(open).toHaveBeenCalledWith('https://example.com', '_blank', 'noopener,noreferrer');
    open.mockRestore();
  });

  it('an anchor keeps its href and its click goes through the bridge', () => {
    const openExternal = vi.fn();
    (window as unknown as { zaram?: unknown }).zaram = { shell: { openExternal } };
    const preventDefault = vi.fn();
    onOpen('https://example.com/docs')({ preventDefault } as unknown as React.MouseEvent<HTMLAnchorElement>);
    expect(preventDefault).toHaveBeenCalled();
    expect(openExternal).toHaveBeenCalledWith('https://example.com/docs');
  });

  it('opens only the web, never a file or a javascript: address', () => {
    expect(isWebAddress('https://a.b')).toBe(true);
    expect(isWebAddress('http://127.0.0.1:5173')).toBe(true);
    expect(isWebAddress('file:///C:/secret')).toBe(false);
    expect(isWebAddress('javascript:alert(1)')).toBe(false);
    expect(isWebAddress(undefined)).toBe(false);
  });

  it('opens local app URLs in the embedded pane', () => {
    (window as unknown as { zaram?: unknown }).zaram = { browser: {} };
    const show = vi.spyOn(useBrowserStore.getState(), 'show');
    for (const url of ['http://localhost:3000', 'http://127.0.0.1:3000', 'http://[::1]:3000']) {
      openAppAddress(url);
      expect(show).toHaveBeenCalledWith(url);
    }
    show.mockRestore();
  });

  it('does not trust deceptive hosts, credentials, or unsafe schemes', () => {
    for (const url of ['https://localhost.example.com', 'https://127.0.0.1.example.com', 'http://user:secret@localhost', 'javascript:alert(1)']) {
      expect(isLocalAppAddress(url)).toBe(false);
    }
    expect(isWebAddress('http://user:secret@localhost')).toBe(false);
  });

  it('keeps external URLs in the system browser and falls back without a desktop bridge', () => {
    const open = vi.spyOn(window, 'open').mockImplementation(() => null);
    openAppAddress('http://localhost:3000');
    expect(open).toHaveBeenCalledWith('http://localhost:3000', '_blank', 'noopener,noreferrer');
    open.mockRestore();
  });
});

