'use strict';

/**
 * Download service foundation.
 *
 * This is an interface/abstraction only — the full download manager (resume,
 * progress, checksum verification, export/import manifests) belongs to a later
 * milestone. For now it records download intent and emits a progress event so
 * the IPC bridge and future UI have a stable contract to build against.
 */
function createDownloadService({ emit, logger }) {
  const downloads = new Map();
  let seq = 0;
  const log = logger || console;

  function notify(id, patch) {
    const current = Object.assign({}, downloads.get(id), patch);
    downloads.set(id, current);
    if (emit) emit(id, current);
  }

  return {
    async start(url, opts) {
      const id = `dl_${++seq}`;
      const record = {
        id,
        url,
        status: 'queued',
        progress: 0,
        createdAt: Date.now(),
        opts: opts || {},
      };
      downloads.set(id, record);
      log.info('Download queued (foundation stub)', { id, url });
      if (emit) emit(id, record);
      return id;
    },
    cancel(id) {
      const d = downloads.get(id);
      if (!d) return;
      notify(id, { status: 'canceled', progress: d.progress });
    },
    list() {
      return Array.from(downloads.values());
    },
  };
}

module.exports = { createDownloadService };
