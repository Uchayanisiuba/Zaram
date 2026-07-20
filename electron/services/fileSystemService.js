'use strict';

const fs = require('fs');
const path = require('path');

/**
 * Sandboxed filesystem service.
 *
 * Only exposes a fixed set of platform-aware roots (user data, logs, downloads,
 * documents, temp). All paths are resolved safely and rejected if they escape
 * the allowed root, so a renderer can never read or write arbitrary files.
 */
function createFileSystemService({ roots, fsImpl }) {
  const impl = fsImpl || fs;

  function resolve(root, rel) {
    const base = roots[root];
    if (!base) throw new Error(`Unknown filesystem root: ${root}`);
    const target = path.resolve(base, rel || '.');
    const baseResolved = path.resolve(base);
    if (target !== baseResolved && !target.startsWith(baseResolved + path.sep)) {
      throw new Error('Path traversal denied');
    }
    return target;
  }

  return {
    getPath: (root) => roots[root] || null,
    readText: (root, rel) => impl.readFileSync(resolve(root, rel), 'utf8'),
    writeText: (root, rel, content) => {
      const target = resolve(root, rel);
      impl.mkdirSync(path.dirname(target), { recursive: true });
      impl.writeFileSync(target, content, 'utf8');
      return true;
    },
    listDir: (root, rel) => impl.readdirSync(resolve(root, rel)),
  };
}

module.exports = { createFileSystemService };
