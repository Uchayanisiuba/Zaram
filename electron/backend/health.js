'use strict';

/**
 * Lightweight backend health probe. Uses an injectable fetch so it is
 * testable without a live server.
 *
 * @param {string} baseUrl
 * @param {string} [healthPath]
 * @param {Function} [fetchImpl]
 * @returns {Promise<{ ok: boolean, status?: number }>}
 */
async function checkHealth(baseUrl, healthPath, fetchImpl) {
  const path = healthPath || '/personalities';
  const doFetch = fetchImpl || (typeof fetch !== 'undefined' ? fetch : null);
  if (!doFetch) throw new Error('fetch is not available in this runtime');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3000);
  try {
    const res = await doFetch(baseUrl + path, {
      method: 'GET',
      signal: controller.signal,
    });
    return { ok: res.ok, status: res.status };
  } finally {
    clearTimeout(timer);
  }
}

module.exports = { checkHealth };
