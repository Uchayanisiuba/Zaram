'use strict';

/**
 * The browser pane: real tabs, over the window, driven by both parties.
 *
 * Asked for 3 October 2026 — *"Zaram users should be able to open new tabs
 * if they need to and go browse the web, while also being able to browse the
 * local host and interact with apps being built with Zaram"*, and on how it
 * should feel, *"all pages are for the user and Zaram to use and drive, I
 * want it to feel like what Claude has."*
 *
 * **Every decision is in `browserPolicy.js` and none are here.** This file
 * creates views, moves them, and forwards what happened. It cannot be
 * covered by `node --test`, so it is kept free of judgement: whether a URL
 * may be opened, whether it needs consent and whether it must be logged are
 * all answered next door, where 42 tests are.
 *
 * A `BrowserView` over the window, not an iframe
 * ----------------------------------------------
 * Most of the web refuses to be framed. The view is a separate `WebContents`
 * positioned by the renderer in CSS pixels and attached above it, which is
 * why `setBounds` is the only layout call here and why the renderer still
 * owns the chrome around it — the tab strip and the address bar are React.
 *
 * Its session is its own
 * ----------------------
 * `persist:zaram-browser`, never the app's default session. The app's
 * session holds the renderer's own origin and the API credential's traffic,
 * and a page the user opened must not share a cookie jar with it. This is
 * the same boundary `RequireApiSecret` draws, one layer out.
 *
 * Every request is reported
 * -------------------------
 * `webRequest.onBeforeSendHeaders` sees every request the pane makes,
 * including the sub-resources a page pulls in. `EgressGate` cannot: it
 * intercepts what the *backend* sends, and nothing here goes through the
 * backend. This is the same hole `CLAUDE.md` names for a VRM's `uri`
 * fetches — *"a request EgressGate cannot see"* — closed in the only place
 * that can see it. Rule 3 is not satisfied by the backend alone once the
 * product has a browser in it.
 */

const { BrowserView, session: electronSession } = require('electron');

const { decideNavigation, egressFor, resolveAddress } = require('./browserPolicy');

/** The pane's own cookie jar, kept away from the renderer's origin. */
const PARTITION = 'persist:zaram-browser';

/** How much of a page title is worth carrying to the tab strip. */
const MAX_TITLE = 120;

function createBrowserService({ logger, getWindow, reportEgress, isBrowseAllowed, emit }) {
  const log = logger || console;
  /** @type {Map<string, {id: string, view: any, url: string, title: string}>} */
  const tabs = new Map();
  let activeId = null;
  let bounds = { x: 0, y: 0, width: 0, height: 0 };
  let nextId = 1;
  let wired = false;

  function paneSession() {
    return electronSession.fromPartition(PARTITION);
  }

  /**
   * Report every request this session makes, once.
   *
   * On the session rather than per view, so a tab opened later is covered
   * without anything remembering to wire it — the shape that produces an
   * unlogged path is the one where each new object has to opt in.
   */
  function wireEgress() {
    if (wired) return;
    wired = true;
    try {
      paneSession().webRequest.onBeforeSendHeaders((details, callback) => {
        try {
          const entry = egressFor(details.url, {
            tabId: String(details.webContentsId || ''),
            initiator: details.referrer || '',
          });
          if (entry) reportEgress(entry);
        } catch (error) {
          // Never let bookkeeping break a page load. The log losing a row
          // is bad; the browser failing to fetch anything is worse, and a
          // throw inside this callback does exactly that.
          log.warn && log.warn(`browser: could not record egress: ${error.message}`);
        }
        callback({ requestHeaders: details.requestHeaders });
      });
    } catch (error) {
      log.error && log.error(`browser: egress reporting not wired: ${error.message}`);
    }
  }

  function publish() {
    emit && emit({
      tabs: [...tabs.values()].map((t) => ({
        id: t.id,
        url: t.url,
        title: t.title,
        active: t.id === activeId,
        canGoBack: safely(() => t.view.webContents.canGoBack(), false),
        canGoForward: safely(() => t.view.webContents.canGoForward(), false),
        loading: safely(() => t.view.webContents.isLoading(), false),
      })),
      activeId,
    });
  }

  function safely(fn, fallback) {
    try {
      return fn();
    } catch {
      return fallback;
    }
  }

  function applyBounds() {
    const tab = tabs.get(activeId);
    if (!tab) return;
    safely(() => tab.view.setBounds(bounds), null);
  }

  function create() {
    wireEgress();
    const id = `tab-${nextId++}`;
    const view = new BrowserView({
      webPreferences: {
        partition: PARTITION,
        // A page the user opened is untrusted by construction. It gets no
        // node, no preload, and no reach into this app's renderer.
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: true,
        webSecurity: true,
      },
    });

    const record = { id, view, url: '', title: 'New tab' };
    tabs.set(id, record);

    const wc = view.webContents;
    wc.on('page-title-updated', (_event, title) => {
      record.title = String(title || '').slice(0, MAX_TITLE);
      publish();
    });
    wc.on('did-navigate', (_event, url) => {
      record.url = url;
      publish();
    });
    wc.on('did-navigate-in-page', (_event, url) => {
      record.url = url;
      publish();
    });
    wc.on('did-start-loading', publish);
    wc.on('did-stop-loading', publish);

    // A page asking for a new window gets a tab, not a popup -- and only if
    // the policy would have allowed typing it.
    wc.setWindowOpenHandler(({ url }) => {
      const decision = decideNavigation(url, { browseAllowed: isBrowseAllowed() });
      if (decision.allow) {
        const opened = create();
        select(opened);
        navigate(opened, url);
      }
      return { action: 'deny' };
    });

    // A navigation the policy refuses is stopped here as well as at
    // `navigate`, because a link click never passes through `navigate`.
    wc.on('will-navigate', (event, url) => {
      if (!decideNavigation(url, { browseAllowed: isBrowseAllowed() }).allow) {
        event.preventDefault();
        emit && emit({ refused: { tabId: id, url } });
      }
    });

    select(id);
    return id;
  }

  function select(id) {
    const window = getWindow && getWindow();
    const tab = tabs.get(id);
    if (!window || !tab) return;
    const previous = tabs.get(activeId);
    if (previous && previous !== tab) safely(() => window.removeBrowserView(previous.view), null);
    safely(() => window.addBrowserView(tab.view), null);
    activeId = id;
    applyBounds();
    publish();
  }

  function navigate(id, typed) {
    const tab = tabs.get(id);
    if (!tab) return { ok: false, reason: 'no-such-tab' };
    const decision = decideNavigation(typed, { browseAllowed: isBrowseAllowed() });
    if (!decision.allow) return decision;
    safely(() => tab.view.webContents.loadURL(decision.url), null);
    tab.url = decision.url;
    publish();
    return decision;
  }

  function close(id) {
    const tab = tabs.get(id);
    if (!tab) return;
    const window = getWindow && getWindow();
    if (window) safely(() => window.removeBrowserView(tab.view), null);
    // Electron 28 has no `BrowserView.destroy()`; closing the contents is
    // what releases the renderer process behind it.
    safely(() => tab.view.webContents.close(), null);
    tabs.delete(id);
    if (activeId === id) {
      activeId = null;
      const next = [...tabs.keys()].pop();
      if (next) select(next);
    }
    publish();
  }

  /**
   * Take every view off the window without closing the tabs.
   *
   * The pane is one surface among six, and a `BrowserView` is *above* the
   * renderer rather than inside it — so a view left attached while the user
   * is in Memory covers Memory. Hiding is the same operation as switching
   * surface, which is why it is separate from `close`.
   */
  function hide() {
    const window = getWindow && getWindow();
    if (!window) return;
    for (const tab of tabs.values()) safely(() => window.removeBrowserView(tab.view), null);
  }

  function show() {
    if (activeId) select(activeId);
  }

  function setBounds(next) {
    bounds = {
      x: Math.max(0, Math.round(next.x || 0)),
      y: Math.max(0, Math.round(next.y || 0)),
      width: Math.max(0, Math.round(next.width || 0)),
      height: Math.max(0, Math.round(next.height || 0)),
    };
    applyBounds();
  }

  function act(id, what) {
    const tab = tabs.get(id);
    if (!tab) return;
    const wc = tab.view.webContents;
    if (what === 'back' && safely(() => wc.canGoBack(), false)) wc.goBack();
    else if (what === 'forward' && safely(() => wc.canGoForward(), false)) wc.goForward();
    else if (what === 'reload') safely(() => wc.reload(), null);
    else if (what === 'stop') safely(() => wc.stop(), null);
    publish();
  }

  function state() {
    return {
      tabs: [...tabs.values()].map((t) => ({
        id: t.id,
        url: t.url,
        title: t.title,
        active: t.id === activeId,
      })),
      activeId,
    };
  }

  return {
    create,
    select,
    navigate,
    close,
    hide,
    show,
    setBounds,
    act,
    state,
    // Exposed for the address bar's "is this even an address" hint, so the
    // renderer does not grow a second opinion about what a URL is.
    resolveAddress,
    PARTITION,
  };
}

module.exports = { createBrowserService, PARTITION };
