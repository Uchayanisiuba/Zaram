'use strict';

/**
 * What the browser pane may open, and what must be recorded when it does.
 *
 * Asked for 3 October 2026: *"Zaram users should be able to open new tabs if
 * they need to and go browse the web, while also being able to browse the
 * local host and interact with apps being built with Zaram"* — and, on the
 * question of how it should feel, *"all pages are for the user and Zaram to
 * use and drive, I want it to feel like what Claude has."*
 *
 * Pure on purpose
 * ---------------
 * No `electron` import, no network, no state. Every rule that decides whether
 * something may be opened lives here so it can be tested without a window,
 * and so the Electron glue beside it has no decisions left to make. The glue
 * is the part that cannot be covered by `node --test`; keeping it decision-free
 * is what stops that mattering.
 *
 * Why a `BrowserView` and not an iframe
 * -------------------------------------
 * Most of the web refuses to be framed — `X-Frame-Options` and CSP
 * `frame-ancestors` are near-universal on the sites anybody would actually
 * open. An iframe-based browser is broken by construction for the open web,
 * and would have shipped looking fine against localhost, which is the only
 * thing it can load. This runs on Electron 28, where `WebContentsView` does
 * not exist yet, so `BrowserView` is the available form.
 *
 * The two rules this file exists to keep
 * --------------------------------------
 * **Loopback is not egress.** A page served from this machine never leaves
 * it, so it needs no consent and is not written to the egress log. That is
 * rule 3 read precisely — *every byte that leaves* — rather than loosely, and
 * reading it loosely would put four hundred entries in the log for one
 * reload of a dev server and drown the entries that matter.
 *
 * **Everything else is egress, and is both consented and logged.** A page the
 * user opens is a request to a host, and `DataClass.BROWSE` is the standing
 * answer for the class. The sub-resources that page pulls in are the reason
 * the class exists at all: one news page is sixty requests to companies the
 * person never chose, so asking per host would be asking about ad networks.
 * They are logged — every one — and not asked about.
 *
 * A scheme allow-list, never a denylist
 * -------------------------------------
 * `electron-builder.yml`'s note applies unchanged: *a denylist fails open*.
 * `javascript:`, `file:`, `data:`, `chrome:` and whatever the next one turns
 * out to be are refused because they are not `http` or `https`, not because
 * they are on a list somebody remembered to write.
 */

/** Schemes the pane will open. Everything else is refused. */
const ALLOWED_SCHEMES = Object.freeze(['http:', 'https:']);

/**
 * Hosts that mean "this machine".
 *
 * `*.localhost` is included because it is reserved for exactly this by
 * RFC 6761 and dev servers use it for subdomain routing. A name that merely
 * *resolves* to 127.0.0.1 is **not** included and must not be: that is the
 * DNS-rebinding shape `CLAUDE.md` records measuring against port 8420, and
 * trusting a hostname because of what it resolves to is how that works.
 */
function isLoopbackHost(host) {
  const name = String(host || '').toLowerCase().replace(/^\[|\]$/g, '');
  if (name === 'localhost' || name.endsWith('.localhost')) return true;
  if (name === '::1') return true;
  // 127.0.0.0/8, all of which is loopback.
  return /^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(name);
}

/**
 * Turn what somebody typed into something to open, or say why not.
 *
 * Returns `{ ok: true, url, scope }` where `scope` is `'local'` or `'web'`,
 * or `{ ok: false, reason, typed }`.
 *
 * **A phrase that is not an address is not silently searched.** Sending it
 * to a search engine would be an egress to a host the person never named,
 * decided by a guess about their intent — so it comes back as `not-an-address`
 * and the pane offers search as something to press. That is also the first
 * rung of the search-then-read-then-browse ladder rather than a detour
 * around it.
 */
function resolveAddress(typed) {
  const text = String(typed == null ? '' : typed).trim();
  if (!text) return { ok: false, reason: 'empty', typed: text };

  // A bare `host:port` parses as a URL whose *scheme* is the host, so the
  // scheme test below would read `localhost:3000` as the scheme `localhost:`
  // and refuse it. Detected before parsing rather than patched after.
  const schemeLike = /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(text);
  const bareHostPort = /^[a-zA-Z0-9.-]+:\d{1,5}(\/|$)/.test(text);

  let candidate = text;
  if (!schemeLike || bareHostPort) {
    const host = text.split('/')[0].split(':')[0];
    // Loopback is served over http in development and nowhere else, so
    // defaulting it to https would make every dev server fail to open.
    // Everything else defaults to https, because defaulting the open web to
    // cleartext is a downgrade chosen on the user's behalf.
    candidate = `${isLoopbackHost(host) ? 'http' : 'https'}://${text}`;
  }

  let parsed;
  try {
    parsed = new URL(candidate);
  } catch {
    return { ok: false, reason: 'not-an-address', typed: text };
  }

  if (!ALLOWED_SCHEMES.includes(parsed.protocol)) {
    return { ok: false, reason: 'scheme', typed: text, scheme: parsed.protocol };
  }
  if (!parsed.hostname) {
    return { ok: false, reason: 'not-an-address', typed: text };
  }
  // Something with no dot and no port is a word, not a host — `tomato`
  // would otherwise become `https://tomato`, which fails to resolve after a
  // DNS lookup has already left the machine.
  if (
    !isLoopbackHost(parsed.hostname) &&
    !parsed.hostname.includes('.') &&
    !parsed.port
  ) {
    return { ok: false, reason: 'not-an-address', typed: text };
  }

  return {
    ok: true,
    url: parsed.toString(),
    scope: isLoopbackHost(parsed.hostname) ? 'local' : 'web',
    host: parsed.hostname,
  };
}

/**
 * May this navigation proceed?
 *
 * `browseAllowed` is the standing answer for `DataClass.BROWSE`, read from
 * the backend's egress policy. Loopback ignores it: nothing leaves the
 * machine, so there is nothing for a consent about sending to govern.
 */
function decideNavigation(typed, { browseAllowed = false } = {}) {
  const resolved = resolveAddress(typed);
  if (!resolved.ok) return { ...resolved, allow: false };
  if (resolved.scope === 'local') return { ...resolved, allow: true, consented: 'not-required' };
  if (!browseAllowed) {
    return { ...resolved, allow: false, reason: 'browse-not-allowed' };
  }
  return { ...resolved, allow: true, consented: 'browse' };
}

/**
 * Should this request be written to the egress log, and as what?
 *
 * Called for **every** request the pane's session makes, including the
 * sub-resources of a page — the ad networks, the fonts, the analytics
 * beacons. Those are the ones the user never chose and the ones the log
 * exists to show them.
 *
 * Returns `null` for anything that did not leave the machine.
 */
function egressFor(requestUrl, { tabId = '', initiator = '' } = {}) {
  let parsed;
  try {
    parsed = new URL(String(requestUrl || ''));
  } catch {
    return null;
  }
  if (!ALLOWED_SCHEMES.includes(parsed.protocol)) return null;
  if (isLoopbackHost(parsed.hostname)) return null;
  return {
    host: parsed.hostname,
    // The path, never the query. A query string carries what was searched
    // for, and the log is read by the person but also shown in screenshots
    // and support threads -- rule 8's posture applied to our own record.
    path: parsed.pathname,
    dataClass: 'browse',
    source: 'browser-pane',
    tabId,
    // Which page pulled this in, so a row for an ad network can be read as
    // "this came from the news site you opened" rather than as something
    // Zaram decided to contact.
    initiator,
  };
}

module.exports = {
  ALLOWED_SCHEMES,
  isLoopbackHost,
  resolveAddress,
  decideNavigation,
  egressFor,
};
