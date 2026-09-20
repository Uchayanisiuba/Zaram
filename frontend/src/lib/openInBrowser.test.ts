import { afterEach, describe, expect, it, vi } from 'vitest';

import { isWebAddress, onOpen, openInBrowser } from './openInBrowser';

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
});

