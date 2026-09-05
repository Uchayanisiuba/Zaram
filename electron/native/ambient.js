'use strict';

/**
 * The ambient surface — Zaram over whatever the user is already looking at.
 *
 * **Why this exists.** Proximity beats capability for habit. An app you have to
 * find loses to a browser tab that is already open, and a memory product only
 * works if the thing it attaches to is opened every day. A global hotkey and a
 * screen-edge handle compete with nothing, because there is nothing to switch
 * to. `CLAUDE.md`, "The ambient surface", calls this the highest-leverage item
 * on the daily-driver list.
 *
 * The pattern is Superhuman Go's and is worth copying closely. **What must not
 * be copied is how it works.** That product reads what you type across
 * applications and sends it to a server; the documented critique is that
 * excluding "sensitive fields" is best-effort by construction, because HTML has
 * no standard way to mark a field sensitive.
 *
 * Invoked, never passive
 * ----------------------
 * **This module installs no hook of any kind.** There is no keyboard listener,
 * no clipboard poll, no focus watcher, no timer. The surface appears when a
 * person presses the accelerator or clicks the handle, and at no other moment.
 * That is a rule rather than a caution — a passive-capture mode is prohibited
 * at any accuracy — and it is why Zaram makes no claim about detecting a
 * password field: it is never reading one.
 *
 * `test/ambient.test.js` asserts the absence at source level rather than
 * describing it, which is the lesson `check-no-cloud-speech.mjs` cost.
 *
 * Warm, because speed is the other half
 * -------------------------------------
 * The panel window is created hidden at boot and shown on demand. A window
 * constructed on the hotkey would pay renderer startup on every summon, which
 * is the difference between an assistant and an irritation — and the whole
 * reason a resident local model is worth having is that there is no network
 * round trip to wait for either.
 *
 * It loads its own entry point, not the main application. The panel is a
 * composer and a reply; the shell is six workspaces and a VRM renderer, and
 * making the fastest surface in the product carry the heaviest bundle in the
 * product would give away the one position the architecture hands over free.
 */

const path = require('path');

/** The default summon key.
 *
 *  Alt+Space is the Windows system menu on a focused window and Ctrl+Space is
 *  taken by half the editors people write in, so neither survives contact with
 *  a real desktop. This combination is unclaimed on Windows and matches the
 *  shape users already know from other launchers. Overridable — it is stored
 *  as a setting, because a global accelerator is exactly the kind of thing that
 *  collides with something only the user knows about. */
const DEFAULT_ACCELERATOR = 'CommandOrControl+Shift+Space';

/** How wide the panel is, and how far down the display it sits. */
const PANEL = { width: 640, height: 420, fromTopFraction: 0.18 };

/** The resting and hovered widths of the edge handle, and how tall it is. */
const HANDLE = { restWidth: 6, hoverWidth: 28, height: 128 };

/**
 * Where the panel goes on the display the user is actually looking at.
 *
 * Keyed off the cursor rather than the main window: the point of an ambient
 * surface is that it appears over the thing in front of you, and on a two
 * monitor desk the main window is frequently on the other one.
 *
 * Clamped into the work area so it never lands under the taskbar or off the
 * edge of a display smaller than the panel.
 *
 * @param {{x:number,y:number,width:number,height:number}} workArea
 * @returns {{x:number,y:number,width:number,height:number}}
 */
function panelBounds(workArea) {
  const width = Math.min(PANEL.width, workArea.width);
  const height = Math.min(PANEL.height, workArea.height);
  const x = Math.round(workArea.x + (workArea.width - width) / 2);
  const y = Math.round(workArea.y + workArea.height * PANEL.fromTopFraction);
  // The vertical clamp is not theoretical: a short work area — a half-height
  // display, or a taskbar docked to the side of a small screen — puts 18% plus
  // the panel height past the bottom edge.
  const maxY = workArea.y + workArea.height - height;
  return { x, y: Math.max(workArea.y, Math.min(y, maxY)), width, height };
}

/**
 * Where the edge handle sits: right edge, vertically centred.
 *
 * The right edge rather than the left because that is where scrollbars and
 * notifications already live, so the handle is in the part of the screen the
 * eye treats as chrome. `hovered` widens it rather than moving it — a target
 * that moves when approached is a target that gets missed.
 */
function handleBounds(workArea, hovered) {
  const width = hovered ? HANDLE.hoverWidth : HANDLE.restWidth;
  const height = Math.min(HANDLE.height, workArea.height);
  return {
    x: workArea.x + workArea.width - width,
    y: Math.round(workArea.y + (workArea.height - height) / 2),
    width,
    height,
  };
}

/**
 * The URL the panel loads.
 *
 * A second Vite entry, so the panel is its own bundle. In development that is
 * the dev server; packaged, it is the static server serving `frontend/dist`.
 * Both are origins the backend already trusts, which matters because the
 * `Host` guard added this session refuses anything else.
 */
function panelUrl(rendererUrl) {
  return `${String(rendererUrl).replace(/\/$/, '')}/ambient.html`;
}

/**
 * @param {object} deps
 * @param {import('../types').DesktopConfig} deps.config
 * @param {{register:Function}} deps.shortcuts  the wrapper from globalShortcuts.js
 * @param {import('../types').Logger} [deps.logger]
 * @param {string} [deps.accelerator]
 * @param {boolean} [deps.enabled]
 */
function createAmbientSurface({ config, shortcuts, logger, accelerator, enabled = true }) {
  const log = logger || console;
  // Required lazily so the geometry above stays importable in plain Node. The
  // same reason `config.js` has no electron import: a module that can only be
  // loaded inside Electron is a module the suite cannot reach.
  const { BrowserWindow, screen } = require('electron');

  const key = accelerator || DEFAULT_ACCELERATOR;
  let panel = null;
  let handle = null;
  // Whether `start()` ran and was permitted to. Without it a disabled surface
  // still answers `ambient:summon` — `summon()` creates the panel when there
  // is none — so a renderer could put an overlay on screen that the user had
  // switched off in settings. A setting the product can overrule is not a
  // setting.
  let running = false;

  /** The display the cursor is on — see `panelBounds`. */
  function currentWorkArea() {
    return screen.getDisplayNearestPoint(screen.getCursorScreenPoint()).workArea;
  }

  function createPanel() {
    const win = new BrowserWindow({
      ...panelBounds(currentWorkArea()),
      show: false,
      frame: false,
      transparent: true,
      resizable: false,
      movable: false,
      minimizable: false,
      maximizable: false,
      fullscreenable: false,
      skipTaskbar: true,
      // Over full-screen applications too. The surface is worthless if it
      // cannot appear above the thing the user is looking at, which is
      // routinely a maximised editor or a presentation.
      alwaysOnTop: true,
      backgroundColor: '#00000000',
      webPreferences: {
        preload: path.join(__dirname, '..', 'preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
        webSecurity: true,
      },
    });
    win.setAlwaysOnTop(true, 'floating');
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

    // Dismiss on blur. Clicking back into your document is the commonest way a
    // person is finished with the panel, and requiring Escape as well would
    // leave it floating over their work.
    win.on('blur', () => dismiss());

    loadWithRetry(win, panelUrl(config.renderer.url));
    return win;
  }

  function createHandle() {
    const win = new BrowserWindow({
      ...handleBounds(currentWorkArea(), false),
      // A hairline is far below the default minimum size, so the minimum is
      // stated rather than assumed. Electron honours the 6px request on
      // Windows either way — measured, after `GetWindowRect` was read as
      // saying otherwise and turned out to be reporting the DWM frame rather
      // than the window. These are insurance against a platform that is less
      // accommodating, not a fix for an observed failure.
      minWidth: 1,
      minHeight: 1,
      show: false,
      frame: false,
      transparent: true,
      resizable: false,
      movable: false,
      skipTaskbar: true,
      alwaysOnTop: true,
      // Never takes focus. The handle sits over other applications all day; if
      // it could steal focus it would interrupt typing, which is precisely the
      // behaviour this product refuses.
      focusable: false,
      backgroundColor: '#00000000',
      webPreferences: {
        preload: path.join(__dirname, '..', 'preload.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: false,
      },
    });
    win.setAlwaysOnTop(true, 'floating');
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
    loadWithRetry(win, `${panelUrl(config.renderer.url)}#handle`);
    return win;
  }

  /**
   * Load, and keep trying if the origin is not up yet.
   *
   * Both overlay windows are created at boot and never reloaded, so a single
   * failed load is permanent: the hotkey then summons a blank rectangle, for
   * the rest of the session, with nothing on screen saying why. The main
   * window cannot hit this because it waits for backend status before loading
   * and reloads on every transition — the overlay has no such cycle, so it
   * needs its own.
   *
   * In development the renderer is a Vite server that may still be starting;
   * packaged, it is the static server, which is listening before this runs.
   * The dev case is the one that fails, and it is also the case where a blank
   * overlay is most likely to be mistaken for a bug in the feature.
   *
   * Bounded, because a retry loop that never gives up hides a real failure
   * behind an infinite quiet.
   */
  function loadWithRetry(win, url, attempt = 0) {
    win.loadURL(url).catch(() => {
      if (win.isDestroyed()) return;
      if (attempt >= 10) {
        log.error('Ambient surface could not load its renderer', { url, attempts: attempt });
        return;
      }
      setTimeout(() => loadWithRetry(win, url, attempt + 1), 500);
    });
  }

  function summon() {
    if (!running) return;
    if (!panel || panel.isDestroyed()) panel = createPanel();
    panel.setBounds(panelBounds(currentWorkArea()));
    panel.show();
    panel.focus();
    log.info('Ambient surface summoned');
  }

  function dismiss() {
    if (panel && !panel.isDestroyed() && panel.isVisible()) panel.hide();
  }

  function toggle() {
    if (panel && !panel.isDestroyed() && panel.isVisible()) dismiss();
    else summon();
  }

  /** Widen or narrow the handle. Called from the renderer on pointer enter and
   *  leave — a hover state the main process cannot observe on its own without
   *  watching the cursor, which is the thing this module does not do. */
  function setHandleHovered(hovered) {
    if (handle && !handle.isDestroyed()) {
      handle.setBounds(handleBounds(currentWorkArea(), Boolean(hovered)));
    }
  }

  function start() {
    if (!enabled) {
      log.info('Ambient surface disabled by setting');
      return { accelerator: null, registered: false };
    }
    running = true;
    // Warm, not eager: created hidden so the first summon is a `show()`.
    panel = createPanel();
    handle = createHandle();
    handle.showInactive();

    // The geometry the platform actually agreed to, not the geometry asked
    // for. A hairline handle is the one dimension a window manager is most
    // likely to overrule, and reading it back from outside — `GetWindowRect`
    // reports the DWM frame, not the window — gave a wrong answer once
    // already. The window is the only thing that knows.
    const geometry = handle && !handle.isDestroyed() ? handle.getBounds() : null;

    const registered = shortcuts.register(key, toggle);
    if (!registered) {
      // Another application owns it. Said plainly rather than swallowed: a
      // hotkey that silently does nothing is indistinguishable from a broken
      // product, and the edge handle still works, which is worth knowing.
      log.warn('Ambient hotkey unavailable; the edge handle still summons', { accelerator: key });
    }
    return { accelerator: key, registered, handle: geometry };
  }

  function destroy() {
    running = false;
    for (const win of [panel, handle]) {
      if (win && !win.isDestroyed()) win.destroy();
    }
    panel = null;
    handle = null;
  }

  return {
    start,
    destroy,
    summon,
    dismiss,
    toggle,
    setHandleHovered,
    getAccelerator: () => key,
    isVisible: () => Boolean(panel && !panel.isDestroyed() && panel.isVisible()),
  };
}

module.exports = {
  createAmbientSurface,
  panelBounds,
  handleBounds,
  panelUrl,
  DEFAULT_ACCELERATOR,
  PANEL,
  HANDLE,
};
