'use strict';

const fs = require('fs');
const path = require('path');

/**
 * Persists user settings as JSON under the platform-aware user data directory.
 * Tolerant of corrupt/missing files so the app always boots.
 */
function createSettingsService({ filePath, fsImpl, defaults }) {
  const impl = fsImpl || fs;
  let cache = null;

  function load() {
    if (cache) return cache;
    try {
      if (impl.existsSync(filePath)) {
        cache = JSON.parse(impl.readFileSync(filePath, 'utf8'));
      } else {
        cache = {};
      }
    } catch (_) {
      cache = {};
    }
    cache = Object.assign({}, defaults || {}, cache);
    return cache;
  }

  function persist() {
    try {
      const dir = path.dirname(filePath);
      if (!impl.existsSync(dir)) impl.mkdirSync(dir, { recursive: true });
      impl.writeFileSync(filePath, JSON.stringify(cache, null, 2), 'utf8');
      return true;
    } catch (_) {
      return false;
    }
  }

  return {
    get(key) {
      return load()[key];
    },
    set(key, value) {
      const c = load();
      c[key] = value;
      persist();
    },
    getAll() {
      return Object.assign({}, load());
    },
  };
}

module.exports = { createSettingsService };
