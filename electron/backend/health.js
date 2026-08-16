'use strict';

/**
 * Lightweight backend health probe. Uses an injectable fetch so it is
 * testable without a live server.
 *
 * **`headers` is not optional in practice.** `/health` requires this launch's
 * API credential like every other route — it reports capabilities, configured
 * providers and model names, which is a description of the user's setup, so it
 * was not made the one exemption. A probe without the credential gets a 401,
 * reports `ok: false`, and the desktop host concludes the backend never came
 * up: the application would sit on its splash screen for ever against a
 * backend that is running perfectly. That is the same symptom as the boot
 * crash fixed earlier and it would have had a completely different cause.
 *
 * @param {string} baseUrl
 * @param {string} [healthPath]
 * @param {Function} [fetchImpl]
 * @param {Record<string,string>} [headers]
 * @returns {Promise<{ ok: boolean, status?: number }>}
 */
async function checkHealth(baseUrl, healthPath, fetchImpl, headers) {
  const path = healthPath || '/personalities';
  const doFetch = fetchImpl || (typeof fetch !== 'undefined' ? fetch : null);
  if (!doFetch) throw new Error('fetch is not available in this runtime');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3000);
  try {
    const res = await doFetch(baseUrl + path, {
      method: 'GET',
      signal: controller.signal,
      headers: headers || {},
    });
    return { ok: res.ok, status: res.status };
  } finally {
    clearTimeout(timer);
  }
}

module.exports = { checkHealth };
