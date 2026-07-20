'use strict';

const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 };

/**
 * Structured logger. Emits JSON lines to an optional file stream and, in dev,
 * to the console. Never blocks the event loop and never uses `print`.
 *
 * @param {object} [options]
 * @param {string} [options.scope]      Logical owner of the log line.
 * @param {import('fs').WriteStream} [options.fileStream]  Destination for JSON lines.
 * @param {string} [options.minLevel]   Minimum level to emit (debug|info|warn|error).
 * @param {boolean} [options.enableConsole]  Mirror to console (dev only).
 * @returns {import('./types').Logger}
 */
function createLogger(options) {
  const o = options || {};
  const scope = o.scope || 'desktop';
  const fileStream = o.fileStream || null;
  const minLevel = LEVELS[o.minLevel || 'info'] || LEVELS.info;
  const enableConsole = o.enableConsole === true;

  function emit(level, msg, meta) {
    const numeric = LEVELS[level] || LEVELS.info;
    if (numeric < minLevel) return;
    const entry = {
      ts: new Date().toISOString(),
      level,
      scope,
      msg,
    };
    if (meta && Object.keys(meta).length) Object.assign(entry, meta);
    const line = JSON.stringify(entry);
    if (fileStream && fileStream.writable) {
      fileStream.write(line + '\n');
    }
    if (enableConsole && level === 'error') console.error(line);
    else if (enableConsole && level === 'warn') console.warn(line);
    else if (enableConsole) console.log(line);
  }

  return {
    debug: (msg, meta) => emit('debug', msg, meta),
    info: (msg, meta) => emit('info', msg, meta),
    warn: (msg, meta) => emit('warn', msg, meta),
    error: (msg, meta) => emit('error', msg, meta),
    child: (subScope) => createLogger({ scope: `${scope}:${subScope}`, fileStream, minLevel: o.minLevel, enableConsole }),
  };
}

module.exports = { createLogger, LEVELS };
