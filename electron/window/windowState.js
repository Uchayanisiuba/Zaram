'use strict';

const fs = require('fs');

function defaultState(config) {
  const w = config.window;
  return {
    width: w.defaultWidth,
    height: w.defaultHeight,
    x: undefined,
    y: undefined,
    maximized: false,
  };
}

function clampBounds(state, minW, minH) {
  const s = Object.assign({}, state);
  if (typeof s.width === 'number') s.width = Math.max(minW, Math.round(s.width));
  if (typeof s.height === 'number') s.height = Math.max(minH, Math.round(s.height));
  return s;
}

function isFiniteNumber(v) {
  return typeof v === 'number' && Number.isFinite(v);
}

/**
 * Load persisted window geometry. Returns safe defaults on any error so the
 * app always boots even with a corrupted state file.
 */
function loadState(filePath, config, fsImpl) {
  const impl = fsImpl || fs;
  const base = defaultState(config);
  try {
    if (!impl.existsSync(filePath)) return base;
    const raw = impl.readFileSync(filePath, 'utf8');
    const parsed = JSON.parse(raw);
    const merged = Object.assign({}, base, parsed);
    return clampBounds(merged, config.window.minWidth, config.window.minHeight);
  } catch (err) {
    return base;
  }
}

/**
 * Persist window geometry. Never throws; a failed save must not crash shutdown.
 */
function saveState(filePath, config, state, fsImpl) {
  const impl = fsImpl || fs;
  try {
    const dir = require('path').dirname(filePath);
    if (!impl.existsSync(dir)) impl.mkdirSync(dir, { recursive: true });
    const toSave = {
      width: isFiniteNumber(state.width) ? Math.round(state.width) : config.window.defaultWidth,
      height: isFiniteNumber(state.height) ? Math.round(state.height) : config.window.defaultHeight,
      x: isFiniteNumber(state.x) ? Math.round(state.x) : undefined,
      y: isFiniteNumber(state.y) ? Math.round(state.y) : undefined,
      maximized: Boolean(state.maximized),
    };
    impl.writeFileSync(filePath, JSON.stringify(toSave, null, 2), 'utf8');
    return true;
  } catch (err) {
    return false;
  }
}

module.exports = { defaultState, clampBounds, loadState, saveState };
