'use strict';

/**
 * Deep link abstraction (foundation / interface only).
 *
 * Registers a protocol handler (`zaram://`) and forwards incoming deep links
 * to the supplied callback. Wiring is done by the main process which owns the
 * `app` lifecycle events.
 *
 * @param {object} [opts]
 * @param {string} [opts.scheme]
 * @param {(url: string) => void} [opts.onDeepLink]
 */
function createDeepLinks({ scheme = 'zaram', onDeepLink } = {}) {
  return {
    scheme,
    onDeepLink,
    /** Forward a raw URL to subscribers (called by main from app events). */
    handle: (url) => {
      if (onDeepLink) onDeepLink(url);
    },
  };
}

module.exports = { createDeepLinks };
