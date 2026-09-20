/**
 * Open a page in the system browser — the only way an external link works
 * in the packaged app.
 *
 * `electron/main.js` `hardenWindow` denies every window-open and every
 * off-app navigation, on purpose: the renderer must not be able to wander.
 * The consequence, found 20 September 2026, is that a plain
 * `<a target="_blank">` does *nothing* when pressed inside Zaram, and four
 * of them had shipped: the GitHub issues link on *Report a problem*,
 * *Where to get a key* under a cloud provider, *running at* on the app card,
 * and every link inside the manual. A dead link on a setup screen reads as
 * the product being broken at the first thing it asks of you.
 *
 * The shell bridge (`window.zaram.shell.openExternal`, an IPC call the main
 * process answers with `shell.openExternal`) is the route. In a plain browser
 * tab during development it does not exist, and `window.open` with
 * `noopener` is the fallback. Nothing here is egress: the browser's request
 * is the person's, made by a program that is not Zaram.
 *
 * `onOpen` is the handler for an anchor that keeps its `href` — so the
 * address is still readable, copyable and reachable by keyboard — while the
 * click goes through here.
 */
import type { MouseEvent } from 'react';

export function openInBrowser(url: string): void {
  const shell = window.zaram?.shell?.openExternal;
  if (typeof shell === 'function') {
    void shell(url);
    return;
  }
  window.open(url, '_blank', 'noopener,noreferrer');
}

/** Only http(s) goes out; anything else stays inert rather than opening. */
export function isWebAddress(url: string | undefined): url is string {
  return typeof url === 'string' && /^https?:\/\//i.test(url);
}

export function onOpen(url: string | undefined) {
  return (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    if (isWebAddress(url)) openInBrowser(url);
  };
}
