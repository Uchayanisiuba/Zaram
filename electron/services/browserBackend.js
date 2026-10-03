'use strict';

/**
 * What the browser pane asks the backend, and tells it.
 *
 * Two jobs, both small, kept out of `main.js` because that file is already
 * 593 lines and `CLAUDE.md` has de-monolithing it on the list.
 *
 * **May a page be opened** — the standing answer for `DataClass.BROWSE`,
 * read from `GET /egress/policy`. Cached with a short life rather than read
 * per request: a page is sixty requests and sixty round trips to answer one
 * question nobody changed in between. Short, because somebody who turns
 * browsing on in Settings should not have to reopen the tab.
 *
 * **What it fetched** — posted to `POST /egress/browse`, which exists
 * because `EgressGate` cannot see any of this. The gate intercepts what the
 * *backend* sends; a `BrowserView` fetches directly from its own Chromium
 * process. Rule 3 says every byte that leaves is logged, and once the
 * product has a browser in it the backend alone no longer satisfies that.
 */

/** How long the standing answer is trusted before it is read again. */
const ANSWER_TTL_MS = 5_000;

/** How long requests are gathered before they are written. */
const FLUSH_MS = 400;

/**
 * The most entries one flush will write.
 *
 * A page that pulls in a thousand resources is a page, not an attack, and
 * the log should say so — but it must not be able to make the renderer
 * unresponsive by queueing faster than this drains. Beyond the cap the
 * overflow is recorded as one row saying how many there were, which is
 * less information and is never a silent loss.
 */
const MAX_PER_FLUSH = 60;

function createBrowserBackend({ baseUrl, getSecret, logger, fetchImpl }) {
  const log = logger || console;
  const doFetch = fetchImpl || globalThis.fetch;

  let allowed = false;
  let readAt = 0;
  let pending = new Map();
  let timer = null;
  let overflowed = 0;

  function headers() {
    return { 'Content-Type': 'application/json', 'X-Zaram-Auth': getSecret() || '' };
  }

  /**
   * Refresh the standing answer.
   *
   * **Fails closed.** A backend that will not answer leaves `allowed` as it
   * was, and it starts `false` — rule 5's default deny survives the backend
   * being down, which is the one condition under which a fail-open default
   * would actually be reached.
   */
  async function refresh() {
    try {
      const response = await doFetch(`${baseUrl}/egress/policy`, { headers: headers() });
      if (!response.ok) return allowed;
      const body = await response.json();
      allowed = (body && body.class_defaults && body.class_defaults.browse) === 'allow';
      readAt = Date.now();
    } catch (error) {
      log.warn && log.warn(`browser: could not read the browsing policy: ${error.message}`);
    }
    return allowed;
  }

  function isBrowseAllowed() {
    if (Date.now() - readAt > ANSWER_TTL_MS) {
      // Fire and forget: this is called from a request handler that cannot
      // wait. The answer in hand is at most `ANSWER_TTL_MS` stale, and the
      // refusal path is a message in the pane rather than a silent failure.
      refresh();
    }
    return allowed;
  }

  function record(entry) {
    if (!entry || !entry.host) return;
    // Deduplicated within the window by host and path. A page that pulls
    // forty fonts from one host is one destination contacted, and forty
    // identical rows make the log harder to read rather than more complete.
    const key = `${entry.host}${entry.path || ''}`;
    if (!pending.has(key)) {
      if (pending.size >= MAX_PER_FLUSH) {
        overflowed += 1;
        return;
      }
      pending.set(key, entry);
    }
    if (!timer) timer = setTimeout(flush, FLUSH_MS);
  }

  async function flush() {
    timer = null;
    const batch = [...pending.values()];
    const missed = overflowed;
    pending = new Map();
    overflowed = 0;
    if (!batch.length) return;

    for (const entry of batch) {
      try {
        await doFetch(`${baseUrl}/egress/browse`, {
          method: 'POST',
          headers: headers(),
          body: JSON.stringify({
            host: entry.host,
            path: entry.path || '/',
            initiator: entry.initiator || '',
            tab_id: entry.tabId || '',
          }),
        });
      } catch (error) {
        // A log write that fails must not break the page that caused it.
        // It is reported here so a user looking at a thin log has
        // something to find.
        log.warn && log.warn(`browser: egress not recorded for ${entry.host}: ${error.message}`);
      }
    }

    if (missed > 0) {
      // Never a silent loss. One row saying how many is less information
      // than the rows themselves and is honest about being less.
      try {
        await doFetch(`${baseUrl}/egress/browse`, {
          method: 'POST',
          headers: headers(),
          body: JSON.stringify({ host: 'zaram.overflow', path: `/${missed}-not-recorded` }),
        });
      } catch {
        /* already degraded; nothing further to try */
      }
    }
  }

  return { isBrowseAllowed, refresh, record, flush };
}

module.exports = { createBrowserBackend, ANSWER_TTL_MS, FLUSH_MS, MAX_PER_FLUSH };
