'use strict';

/**
 * Give the card back on the way out.
 *
 * The backend's `POST /providers/release` unloads every model every local
 * server can unload — the "I am about to open Unreal" button in Settings.
 * Until 20 September 2026 nothing pressed it on quit, and the host stops the
 * backend with `child.kill()`, which on Windows is a hard terminate: the
 * backend's own shutdown never runs, so a person who closed Zaram and opened
 * Unreal found the card still held by a model nobody was talking to.
 *
 * Bounded, and never a reason not to quit. A backend that is hung or gone
 * answers nothing; the quit proceeds after `timeoutMs` exactly as it would
 * have, and the outcome is logged rather than surfaced — there is no window
 * left to surface it in. Loopback only, never egress.
 *
 * Injectable fetch so it is testable without a live server, like `health.js`.
 *
 * @param {string} baseUrl
 * @param {Record<string,string>} headers  the launch credential
 * @param {{ fetchImpl?: Function, timeoutMs?: number }} [options]
 * @returns {Promise<{ released: boolean, status?: number, error?: string }>}
 */
async function releaseCard(baseUrl, headers, options) {
  const opts = options || {};
  const doFetch = opts.fetchImpl || (typeof fetch !== 'undefined' ? fetch : null);
  if (!doFetch) return { released: false, error: 'fetch is not available in this runtime' };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs || 4000);
  try {
    const res = await doFetch(baseUrl + '/providers/release', {
      method: 'POST',
      signal: controller.signal,
      headers: headers || {},
    });
    return { released: res.ok, status: res.status };
  } catch (err) {
    return { released: false, error: (err && err.message) || String(err) };
  } finally {
    clearTimeout(timer);
  }
}

module.exports = { releaseCard };
