/**
 * Code a reply can show rather than only print.
 *
 * Why this exists
 * ---------------
 * Assistant replies render as `whitespace-pre-wrap` in `ChatSurface` — plain
 * preformatted text, no markdown, no code blocks. So a model asked for a web
 * page produced a perfectly good document that the product could only display
 * as characters. `ArtifactPreview` could already render generated HTML in a
 * sandboxed frame, but it is addressed by artifact id, and nothing in the
 * interface calls `POST /artifacts/generate` — so that renderer was reachable
 * only for files the app had no way to make.
 *
 * This module is the half that was missing: find the previewable block in a
 * reply, and wrap it the same way the artifact path wraps a document.
 *
 * The wrapping is shared, deliberately
 * ------------------------------------
 * `CSP` and `FRAME_STYLE` live here and are imported by both preview surfaces.
 * Two copies of a security header is the drift this codebase has paid for
 * elsewhere — the one that matters gets edited and the other keeps a weaker
 * rule, with nothing reporting it.
 *
 * What counts as previewable
 * --------------------------
 * HTML and SVG, and nothing else. Both are *rendered* by a browser with no
 * interpreter of ours involved. A fenced `python` or `bash` block is a
 * different proposition entirely — running it is the mutative tier, which
 * `CLAUDE.md` puts out of scope until undo, confirm and sandbox exist — so it
 * is deliberately not offered here. "Preview" must never come to mean
 * "execute".
 */

import { bundleApp, extractAppFiles, type AppFile } from './appFiles';

/** For a generated **document** — an invoice, a report, a CV.
 *
 *  Blocks every remote sub-resource the document might name. `sandbox=""`
 *  already denies scripts and same-origin, but it does not stop an `<img>`
 *  fetching a remote URL, and that fetch is a beacon carrying the user's IP
 *  and the moment they opened the file — a request `EgressGate` cannot see,
 *  because that intercepts what the *backend* sends.
 *
 *  A document has no reason to run a script, so it does not get to. */
export const DOCUMENT_CSP =
  "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; " +
  "style-src 'unsafe-inline'; img-src data:; font-src data:;\">";

/** For a **page written in a reply** — something with behaviour.
 *
 *  Differs from `DOCUMENT_CSP` in exactly one clause: inline script is
 *  permitted. Everything else is unchanged, and `default-src 'none'` is what
 *  carries the weight — it covers `connect-src`, so `fetch`, `XMLHttpRequest`,
 *  `WebSocket` and `EventSource` are all refused. A script may compute; it may
 *  not phone anywhere.
 *
 *  **Why this is not the mutative tier.** The tier table grades by
 *  *consequence*, not by whether code runs. Paired with `allow-scripts` and
 *  **no** `allow-same-origin`, the frame gets an opaque origin: no reach into
 *  this app's DOM or storage, its own storage isolated and discarded, no
 *  network, no navigation, no popups, no modals. That last claim was
 *  aspirational until `SEALED_STORAGE` below made it true — an opaque origin
 *  does not give a frame isolated storage, it gives it storage that throws. The consequence is that
 *  pixels change. That is the generative tier, and the first version of this
 *  file refused it by applying the label instead of the test — which left a
 *  calculator that could not add up.
 *
 *  **`'unsafe-eval'` is granted, and withholding it was a mistake.** The first
 *  version left it out on the general principle that a string-to-code
 *  primitive is worth refusing. That principle is about pages with privileges
 *  to lose: `eval` matters because it turns injected text into code *inside an
 *  origin that can do something*. This frame has no origin worth reaching, no
 *  network, no storage and no parent, and inline script is already permitted —
 *  so a page here can run whatever it likes with or without `eval`, and
 *  refusing it removed no capability from an attacker while removing a great
 *  deal from a calculator. Generated arithmetic reaches for `eval` constantly,
 *  and what the refusal produced was a UI that rendered perfectly and did
 *  nothing when you pressed equals. Same error as `sandbox=""`: grading by the
 *  name of the capability instead of by its consequence here. */
export const APP_CSP = appCsp();

/** The same policy, optionally letting named hosts in.
 *
 * **Nothing is allowed by default, and that has not changed.** Called
 * with no hosts this is byte-for-byte the policy above, which is the one
 * every preview starts under.
 *
 * **Why hosts can be named at all — 4 October 2026.** A page that says
 * `<script src="https://cdn.jsdelivr.net/npm/three">` renders as a black
 * rectangle, and the maintainer asked for Three.js previews directly.
 * The refusal was not a bug: a remote sub-resource is a request carrying
 * the user's IP and the moment they opened the page, and `EgressGate`
 * cannot see it because that intercepts what the *backend* sends.
 *
 * So the fix is not to open the policy — it is to ask. The frame already
 * reports what it was refused (`ERROR_REPORTER`), the panel already names
 * the host, and rule 5 says default deny with an explicit per-item
 * decision. The person presses allow for that host, the preview reloads
 * under a policy naming it, and the egress is recorded. One host, one
 * preview, one decision — not a standing allow-list somebody has to
 * audit later.
 *
 * `connect-src` is deliberately **not** widened. A library fetched by
 * `<script src>` is a thing the person agreed to load; `fetch()` from
 * inside the page to the same host is the page talking back, which is a
 * different act and was not what was allowed.
 */
export function appCsp(hosts: readonly string[] = [], libraries = false): string {
  // Normalised and bounded. A host arrives from a CSP violation report,
  // which is text the *page* influenced, so it is matched against a
  // hostname shape rather than pasted into a policy. A page that could
  // write `*` into this would have talked its way out of the sandbox.
  const named = [...new Set(hosts)]
    .filter((h) => /^[a-z0-9.-]+$/i.test(h) && h.includes('.'))
    .slice(0, 8)
    .map((h) => `https://${h}`);
  const extra = named.length ? ' ' + named.join(' ') : '';
  return (
    '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; ' +
    // `data:` only when Zaram serves a library as a module (see
    // `previewLibraries.ts`): an import map can only point at a URL, and a
    // page that may already run inline script and `eval` gains nothing from
    // a module written into a data URL.
    `script-src \'unsafe-inline\' \'unsafe-eval\'${libraries ? ' data:' : ''}${extra}; ` +
    `style-src \'unsafe-inline\'${extra}; ` +
    `img-src data:${extra}; font-src data:${extra};">`
  );
}

/** Injected ahead of the page so a failure is reported rather than silent.
 *
 *  A preview that renders and then does nothing is the worst outcome the panel
 *  can produce: it looks like the model wrote broken code, when it may equally
 *  be the frame refusing something. The parent cannot read into an opaque
 *  origin to find out — so the frame volunteers it, over `postMessage`.
 *
 *  Errors only, and never the page's own console noise: this is a fault
 *  channel, not a log. `securitypolicyviolation` is included because a CSP
 *  refusal is exactly the failure a user would otherwise have no way to see,
 *  and it is the one this file has now caused twice. */
export const ERROR_REPORTER = `<script>
(function () {
  function send(kind, detail, uri) {
    try { parent.postMessage({ __zaramPreview: true, kind: kind, detail: String(detail), uri: String(uri || '') }, '*'); }
    catch (e) { /* nothing to be done from in here */ }
  }
  window.addEventListener('error', function (e) {
    send('error', (e && e.message) || 'script error');
  });
  window.addEventListener('unhandledrejection', function (e) {
    send('error', (e && e.reason && e.reason.message) || 'unhandled rejection');
  });
  document.addEventListener('securitypolicyviolation', function (e) {
    send('blocked', (e.violatedDirective || 'policy') + ' blocked ' + (e.blockedURI || 'inline'), e.blockedURI);
  });
})();
<\/script>`;

/** Storage the page can use, that is a map in this frame and nothing else.
 *
 *  **This is the bug that made a working Tetris look broken.** `allow-scripts`
 *  without `allow-same-origin` gives the frame an opaque origin, and in an
 *  opaque origin `window.localStorage` does not return an empty store — it
 *  *throws* `SecurityError` on the very first read. A generated game opens
 *  with `parseInt(localStorage.getItem('highScore') || '0')`, that line throws
 *  at the top level, and every line after it never runs. The page renders,
 *  the canvas stays black, nothing responds to a key. Measured: the panel's
 *  own reporter caught it as "Uncaught SecurityError: Failed to read the
 *  'localStorage' property from 'Window'". A portfolio page hits the same wall
 *  reading a saved theme, which is why both symptoms arrived together.
 *
 *  So the frame is handed its own. An in-memory map, installed before the
 *  page's script runs, discarded with the frame — it touches no disk, no
 *  origin and nothing of this app's. **That is strictly less than real
 *  storage, not more**, which is why it does not widen the seal: the reason
 *  real `localStorage` would be wrong here is that it would be *Zaram's*
 *  origin, persisting across previews. This persists across nothing.
 *
 *  Same grading as `'unsafe-eval'` above, and the same lesson twice: refusing
 *  by the *name* of a capability rather than by its consequence here is what
 *  produced a calculator that could not add up, and now a game that could not
 *  start.
 *
 *  `document.cookie` throws identically and gets the same treatment. Cookies
 *  are a store with names, so it keeps names rather than appending forever —
 *  no expiry, no domains, no path, because a preview that ends when the panel
 *  closes has no use for any of them.
 *
 *  **`indexedDB` is deliberately not shimmed.** `indexedDB.open` throws the
 *  same `SecurityError`, and a half-built fake database would fail later,
 *  deeper, and less legibly than the honest error does now. A generated page
 *  reaching for IndexedDB is rare; one that does gets a reported fault, which
 *  is the outcome this file exists to guarantee. */
export const SEALED_STORAGE = `<script>
(function () {
  function memory() {
    var map = Object.create(null);
    var base = {
      getItem: function (key) { key = String(key); return key in map ? map[key] : null; },
      setItem: function (key, value) { map[String(key)] = String(value); },
      removeItem: function (key) { delete map[String(key)]; },
      clear: function () { for (var key in map) { delete map[key]; } },
      key: function (index) { var keys = Object.keys(map); return index in keys ? keys[index] : null; }
    };
    // A Proxy rather than a plain object because real storage answers to
    // localStorage.highScore as well as to getItem('highScore'), and generated
    // pages use both spellings interchangeably.
    return new Proxy(base, {
      get: function (target, name) {
        if (name === 'length') return Object.keys(map).length;
        if (name in target) return target[name];
        return typeof name === 'string' && name in map ? map[name] : undefined;
      },
      set: function (target, name, value) {
        if (!(name in target)) map[String(name)] = String(value);
        return true;
      },
      deleteProperty: function (target, name) { delete map[String(name)]; return true; },
      has: function (target, name) { return name in target || name in map; },
      ownKeys: function () { return Object.keys(map); },
      getOwnPropertyDescriptor: function (target, name) {
        if (name in map) return { value: map[name], writable: true, enumerable: true, configurable: true };
        return undefined;
      }
    });
  }
  // An own property on the window shadows the throwing accessor it inherits.
  var names = ['localStorage', 'sessionStorage'];
  for (var i = 0; i < names.length; i++) {
    try { Object.defineProperty(window, names[i], { value: memory(), configurable: true }); }
    catch (e) { /* a frame that still loads beats one that does not */ }
  }
  try {
    var jar = Object.create(null);
    Object.defineProperty(document, 'cookie', {
      configurable: true,
      get: function () {
        return Object.keys(jar).map(function (k) { return k + '=' + jar[k]; }).join('; ');
      },
      set: function (value) {
        var pair = String(value).split(';')[0];
        var eq = pair.indexOf('=');
        if (eq > 0) { jar[pair.slice(0, eq).trim()] = pair.slice(eq + 1).trim(); }
      }
    });
  } catch (e) { /* as above */ }
})();
<\/script>`;

/** Pause and resume for a page that moves.
 *
 *  Asked for 4 October 2026 as "playback and review on the HTML surface": the
 *  voxel world, the runner and the CSS loop all move, and a panel that can only
 *  show them running cannot be paused to read, or restarted to see the opening
 *  again. The frame has an opaque origin, so the parent cannot reach in — the
 *  page is handed a listener instead, as the error reporter and the storage shim
 *  are, and told by `postMessage`.
 *
 *  What pausing means here, honestly:
 *
 *  * **CSS animations and transitions** stop, by a rule on every element.
 *  * **`requestAnimationFrame`, `setTimeout` and `setInterval` callbacks are
 *    held, not dropped**, and released on resume. A game loop is one of those
 *    three, so the game stops advancing and carries on from where it was. A
 *    held interval fires once on resume rather than once per missed tick.
 *  * **It does not stop everything.** A page that animates from a Web Worker, an
 *    audio element or a video keeps going; a game that measures real time may
 *    jump forward on resume. The control says "pause", not "freeze", and this is
 *    the reason.
 *
 *  Only the parent is listened to (`event.source === parent`): a sandboxed page
 *  has no business taking orders from a stranger, and the message carries no
 *  data a page could use anyway.
 *
 *  The body is a function of `win`, so a test can hand it a fake window and
 *  watch it hold and release callbacks without a browser. */
export const PLAYBACK = `<script>
(function (win) {
  var paused = false;
  var held = [];
  var rafNative = win.requestAnimationFrame && win.requestAnimationFrame.bind(win);
  var timeoutNative = win.setTimeout.bind(win);
  var intervalNative = win.setInterval.bind(win);
  var style = null;

  function hold(fn, args) { held.push({ fn: fn, args: args }); }

  if (rafNative) {
    win.requestAnimationFrame = function (callback) {
      return rafNative(function (time) {
        if (paused) { hold(callback, [time]); } else { callback(time); }
      });
    };
  }
  win.setTimeout = function (callback) {
    var extra = Array.prototype.slice.call(arguments, 2);
    if (typeof callback !== 'function') { return timeoutNative.apply(win, arguments); }
    var delay = arguments[1];
    return timeoutNative(function () {
      if (paused) { hold(callback, extra); } else { callback.apply(win, extra); }
    }, delay);
  };
  win.setInterval = function (callback) {
    var extra = Array.prototype.slice.call(arguments, 2);
    if (typeof callback !== 'function') { return intervalNative.apply(win, arguments); }
    var delay = arguments[1];
    var queued = false;
    return intervalNative(function () {
      if (paused) {
        // One held tick however long the pause: a backlog of every missed beat
        // released at once would make a paused game lurch.
        if (!queued) { queued = true; hold(function () { queued = false; callback.apply(win, extra); }, []); }
      } else { callback.apply(win, extra); }
    }, delay);
  };

  function setPaused(next) {
    if (next === paused) { return; }
    paused = next;
    try {
      if (paused) {
        style = win.document.createElement('style');
        style.textContent = '*, *::before, *::after { animation-play-state: paused !important; transition: none !important; }';
        (win.document.head || win.document.documentElement).appendChild(style);
      } else if (style && style.parentNode) {
        style.parentNode.removeChild(style);
        style = null;
      }
    } catch (e) { /* the callbacks matter more than the stylesheet */ }
    if (!paused) {
      var release = held; held = [];
      for (var i = 0; i < release.length; i++) {
        try { release[i].fn.apply(win, release[i].args); }
        catch (e) { try { win.parent.postMessage({ __zaramPreview: true, kind: 'error', detail: String(e && e.message || e), uri: '' }, '*'); } catch (x) {} }
      }
    }
  }

  win.addEventListener('message', function (event) {
    if (event.source !== win.parent) { return; }
    var data = event.data;
    if (!data || data.__zaramPreviewControl !== true) { return; }
    if (data.action === 'pause') { setPaused(true); }
    else if (data.action === 'play') { setPaused(false); }
  });
})(window);
<\/script>`;

/** Pointing at part of the page — 5 October 2026.
 *
 *  Off until the panel's **Select** is pressed, because a page owns its own
 *  clicks: a block game places a block on right-click, and a picker that
 *  always took the right button would break the thing it is meant to help
 *  change. While on, the pointer outlines what is under it and a click or a
 *  right-click picks it; nothing reaches the page until Select is pressed
 *  again or Escape is.
 *
 *  Listeners go on the window in the capture phase, ahead of anything the
 *  page registers, so a picking click never also fires the page's own
 *  handler. What is reported is a description — tag, a short selector, the
 *  visible text, the start of the markup — and the parent treats all of it as
 *  page-controlled text (`askAboutPage.readPick`). */
export const PICKER = `<script>
(function (win, doc) {
  var on = false, box = null, current = null;
  function ensureBox() {
    if (box) { return box; }
    box = doc.createElement('div');
    var s = box.style;
    s.position = 'fixed'; s.pointerEvents = 'none'; s.zIndex = '2147483647';
    s.border = '2px solid #22d3ee'; s.background = 'rgba(34,211,238,0.12)';
    s.borderRadius = '3px'; s.boxSizing = 'border-box'; s.display = 'none';
    (doc.body || doc.documentElement).appendChild(box);
    return box;
  }
  function outline(el) {
    var r = el.getBoundingClientRect(), b = ensureBox();
    b.style.display = 'block';
    b.style.left = r.left + 'px'; b.style.top = r.top + 'px';
    b.style.width = r.width + 'px'; b.style.height = r.height + 'px';
  }
  function hide() { if (box) { box.style.display = 'none'; } }
  function step(el) {
    var name = el.tagName.toLowerCase();
    if (el.id) { return name + '#' + el.id; }
    var cls = (typeof el.className === 'string' ? el.className : '').trim().split(/\\s+/).filter(Boolean).slice(0, 2);
    if (cls.length) { name += '.' + cls.join('.'); }
    var parent = el.parentElement;
    if (parent) {
      var same = 0, index = 0;
      for (var i = 0; i < parent.children.length; i++) {
        if (parent.children[i].tagName === el.tagName) { same++; if (parent.children[i] === el) { index = same; } }
      }
      if (same > 1) { name += ':nth-of-type(' + index + ')'; }
    }
    return name;
  }
  function selector(el) {
    var parts = [], node = el;
    while (node && node.nodeType === 1 && parts.length < 5 && node !== doc.documentElement) {
      parts.unshift(step(node));
      if (node.id) { break; }
      node = node.parentElement;
    }
    return parts.join(' > ');
  }
  function target(e) {
    var t = e.target;
    return t && t.nodeType === 1 && t !== box ? t : null;
  }
  function over(e) {
    if (!on) { return; }
    var t = target(e);
    if (t) { current = t; outline(t); }
  }
  function pick(e) {
    if (!on) { return; }
    e.preventDefault(); e.stopImmediatePropagation();
    var t = target(e) || current;
    if (!t) { return; }
    outline(t);
    var r = t.getBoundingClientRect();
    var html = t.outerHTML || '';
    try {
      parent.postMessage({ __zaramPreview: true, kind: 'picked', detail: JSON.stringify({
        tag: t.tagName.toLowerCase(),
        selector: selector(t),
        text: (t.innerText || t.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 160),
        html: html.length > 800 ? html.slice(0, 800) : html,
        rect: { x: r.left, y: r.top, w: r.width, h: r.height }
      }) }, '*');
    } catch (err) { /* nothing to be done from in here */ }
  }
  function swallow(e) { if (on) { e.preventDefault(); e.stopImmediatePropagation(); } }
  win.addEventListener('mouseover', over, true);
  win.addEventListener('click', pick, true);
  win.addEventListener('contextmenu', pick, true);
  ['mousedown', 'mouseup', 'pointerdown', 'pointerup', 'dblclick', 'auxclick'].forEach(function (type) {
    win.addEventListener(type, swallow, true);
  });
  win.addEventListener('keydown', function (e) {
    if (on && e.key === 'Escape') {
      try { parent.postMessage({ __zaramPreview: true, kind: 'pick-cancel', detail: '' }, '*'); } catch (err) {}
    }
  }, true);
  win.addEventListener('message', function (event) {
    if (event.source !== win.parent) { return; }
    var data = event.data;
    if (!data || data.__zaramPreviewControl !== true || data.action !== 'pick') { return; }
    on = data.on === true;
    if (on) {
      if (doc.pointerLockElement && doc.exitPointerLock) { try { doc.exitPointerLock(); } catch (err) {} }
      doc.documentElement.style.cursor = 'crosshair';
    } else {
      hide(); current = null;
      doc.documentElement.style.cursor = '';
    }
  });
})(window, document);
<\/script>`;

/** A loop that cannot end, found by reading the source.
 *
 *  Found 5 October 2026 on a Minecraft-style page the resident model wrote:
 *  `for(let i=0;i<16;i)for(...)` — the `++` missing — twenty-three times, in
 *  the code that draws the hotbar icons. `i` never changes, the loop never
 *  ends, and the page froze before drawing anything. A frame cannot be
 *  interrupted from outside while it is stuck in one, and in a browser tab the
 *  whole tab goes with it, so the only safe moment to catch it is before it
 *  runs.
 *
 *  **One shape, because it is the one that is certain enough to say.** A
 *  `for` whose update clause is a bare name (`i`) does nothing on every turn.
 *  It only ends if the body changes the variable itself or leaves the loop, so
 *  the answer is "very likely", and the panel offers *Run anyway*. A general
 *  halting check is not on offer and this does not pretend to be one: `while
 *  (true)` is how every game loop is written, and flagging it would teach
 *  people to click past the warning. */
export interface StuckLoop {
  /** 1-based line in the model's page. */
  line: number;
  /** The loop header as written, trimmed. */
  text: string;
}

const BARE_UPDATE = /for\s*\(\s*(?:let|var|const)?\s*([A-Za-z_$][\w$]*)\s*=[^;()]*;[^;()]*;\s*\1\s*\)/g;

export function findStuckLoop(source: string): StuckLoop | null {
  BARE_UPDATE.lastIndex = 0;
  const match = BARE_UPDATE.exec(source);
  if (!match) return null;
  return {
    line: source.slice(0, match.index).split('\n').length,
    text: match[0].replace(/\s+/g, ' ').slice(0, 80),
  };
}

/** The sandbox the app frame runs under.
 *
 *  **`allow-same-origin` must never join this list.** Granted alongside
 *  `allow-scripts` it does not merely widen the sandbox, it dissolves it: the
 *  frame would share this app's origin and could reach in and remove its own
 *  `sandbox` attribute. The two together are the documented footgun, and
 *  `previewableCode.test.ts` asserts against it directly rather than trusting
 *  a comment to be read. */
//:
// **`allow-pointer-lock` added 5 October 2026.** A first-person game starts by
// locking the pointer on a click; without the flag the request fails, the
// page's "click to start" overlay never clears, and the game cannot be
// played. Pointer lock reaches nothing outside the frame — it hides the
// cursor and reports mouse movement to the page — and Escape always releases
// it, which the browser guarantees and no page can override.
export const APP_SANDBOX = 'allow-scripts allow-pointer-lock';

/** A readable page rather than the browser's default serif on white. */
export const FRAME_STYLE = `<style>
  html, body { margin: 0; padding: 24px; background: #fff; color: #111;
               font: 14px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif; }
  img, table { max-width: 100%; }
  table { border-collapse: collapse; }
  td, th { border: 1px solid #ddd; padding: 6px 8px; }
</style>`;

/** What the frame is handed: the model's markup behind our CSP and styling.
 *
 *  The CSP goes first so it is in force before anything the document declares.
 *  A generated page carrying its own `<meta http-equiv>` cannot loosen ours —
 *  the restrictive policy of the two wins by specification.
 *
 *  `mode` picks which policy applies. `'document'` is the generated-artifact
 *  path and runs nothing; `'app'` is a page written in a reply and may run its
 *  own inline script, still with no way to reach the network. Two policies
 *  rather than one permissive policy for both, because an invoice gaining the
 *  ability to execute would be surface bought for nothing. */
export function wrapForPreview(
  source: string,
  mode: 'document' | 'app' = 'document',
  /** Hosts the person has allowed for *this* preview. Empty by default;
   *  see `appCsp`. A document never gets these — an invoice has no
   *  reason to reach anywhere, and granting it one would be surface
   *  bought for nothing. */
  allowedHosts: readonly string[] = [],
  /** Libraries Zaram serves this page from its own copy, already rendered as
   *  markup by `previewLibraries.vendorPage`. Empty for most pages. */
  libraries = '',
): string {
  if (mode !== 'app') return DOCUMENT_CSP + FRAME_STYLE + source;
  // Three things ahead of the page, and the order of all three is load-bearing.
  // The reporter is first so it is listening while everything after it runs —
  // registered later it would miss the errors that matter most, which are the
  // ones thrown during setup, and it would not be able to report a shim that
  // failed to install. The shim is next because it has to be in place before
  // the page's *first* line: the storage read that broke Tetris was line one.
  // Playback goes last of the three: it wraps the timers the page is about to
  // use, so it must be in place before the page's first line, and it needs the
  // reporter already listening for a callback that throws on resume.
  // **No `FRAME_STYLE` for an app — 5 October 2026.** Its 24px of padding
  // and white page are right for a document and wrong for anything that
  // draws to the whole window: a game sized to `innerWidth` sat inset under
  // a black band, with a scrollbar. An app is shown as the browser would show
  // the saved file, which is the promise the preview exists to keep.
  // The libraries go last of the prefix: after the reporter, so a library
  // that fails to start is reported, and before the page, which uses them.
  return (
    appCsp(allowedHosts, Boolean(libraries)) +
    ERROR_REPORTER +
    SEALED_STORAGE +
    PLAYBACK +
    PICKER +
    libraries +
    source
  );
}

/** The languages worth offering a preview for, and the label each gets. */
const PREVIEWABLE: Record<string, string> = {
  html: 'HTML',
  svg: 'SVG',
};

export interface PreviewableBlock {
  /** Lower-cased fence language, one of the keys above. */
  language: string;
  /** Human label for the button and the panel heading. */
  label: string;
  /** The block's contents, verbatim. For an app of several files, the files
   *  already joined into the one page the frame runs. */
  code: string;
  /** Present when the reply wrote an app of several named files. `code` is
   *  their joined form; these are what is shown as code and what is saved. */
  files?: AppFile[];
  /** Whether the joined page loads modules from `data:` URLs, so its policy
   *  has to allow them. */
  modules?: boolean;
}

/**
 * The first previewable fenced block in a reply, or `null`.
 *
 * First rather than all of them: the affordance is one button under one
 * message, and a reply containing two pages is rare enough that guessing wrong
 * costs a click rather than a misunderstanding.
 *
 * Tolerant of an unclosed fence, because this runs against text that is still
 * streaming. A block that has opened but not closed yet is returned with what
 * has arrived so far, so the button appears when the code does rather than a
 * beat after it — and the panel re-reads on each render, so it fills in.
 */
export function extractPreviewable(text: string): PreviewableBlock | null {
  if (!text) return null;

  // An app of several named files is one thing to run, so it is read first:
  // its page alone would show unstyled and do nothing.
  const files = extractAppFiles(text);
  const bundled = files ? bundleApp(files) : null;
  if (files && bundled) {
    return { language: 'html', label: 'App', code: bundled.html, files, modules: bundled.modules };
  }

  // ```html … ``` — the fence language may carry extra words (```html title=x)
  // which are ignored, and the closing fence is optional while streaming.
  const fence = /```[ \t]*([A-Za-z][\w+-]*)[^\n]*\n([\s\S]*?)(?:```|$)/g;

  let match: RegExpExecArray | null;
  while ((match = fence.exec(text)) !== null) {
    const language = match[1].toLowerCase();
    const label = PREVIEWABLE[language];
    if (!label) continue;
    const code = match[2];
    if (!code.trim()) continue;
    return { language, label, code };
  }

  return null;
}

/** What to call the file when a page written in a reply is saved.
 *
 *  Read from the page's own `<title>` where it has one, because a model that
 *  wrote a budget calculator titled it "Budget calculator" and that is a
 *  better name than anything this module could invent. Falls back to the
 *  language — `page.html`, `image.svg` — rather than to a timestamp: a name
 *  nobody can read is not more informative for being unique, and the operating
 *  system already disambiguates a second `page.html` on its own.
 *
 *  The result is deliberately conservative — lower case, ASCII words joined by
 *  hyphens, one extension. It reaches `<a download>`, which is a hint the
 *  browser sanitises anyway, and beyond that it lands in a real directory on
 *  three operating systems with different opinions about what a filename may
 *  contain. Producing something dull that works everywhere is the whole job. */
export function filenameFor(block: PreviewableBlock): string {
  if (block.files) return `${block.files.length} files, as a folder`;
  const extension = block.language === 'svg' ? 'svg' : 'html';
  const titled = /<title[^>]*>([\s\S]*?)<\/title>/i.exec(block.code);
  const slug = (titled?.[1] ?? '')
    .replace(/&[a-z]+;|&#\d+;/gi, ' ')
    .replace(/[^A-Za-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
    .slice(0, 60);
  return `${slug || (extension === 'svg' ? 'image' : 'page')}.${extension}`;
}

/** Save a page written in a reply to disk, as the file it already is.
 *
 *  **What is saved is the model's markup, not what the preview frame runs.**
 *  `wrapForPreview` prepends our CSP, our stylesheet and the fault reporter,
 *  and every one of those is scaffolding for showing the page *here*. Writing
 *  them into the user's file would hand them a document with a policy meta tag
 *  they did not ask for, a `postMessage` call to a parent that no longer
 *  exists, and body styling that overrides their own. The preview is a lens;
 *  the file is what was written.
 *
 *  Blob, object URL, synthesised click, revoke — the same machinery as
 *  `downloadArtifact` in `services/artifactsClient`, and for a related reason:
 *  a plain `<a href>` is not the shape that works here. There it was the API
 *  credential a link cannot carry; here there is no URL to link to at all,
 *  because the file exists only as a string in this tab. The revoke is
 *  deferred for the same measured reason it is there — Chrome cancels a
 *  download whose object URL is released before it has finished reading it. */
export function savePreviewable(block: PreviewableBlock): Promise<string | null> {
  // An app of several files is a folder, and a browser download is one file.
  // It is written to Zaram's output directory instead -- new files only, no
  // project -- and the folder is named back to the person.
  if (block.files) return saveAppFolder(block);
  const type = block.language === 'svg' ? 'image/svg+xml' : 'text/html';
  const url = URL.createObjectURL(new Blob([block.code], { type: `${type};charset=utf-8` }));
  try {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filenameFor(block);
    anchor.style.display = 'none';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  }
  return Promise.resolve(null);
}

/** Keep an app of several files as a new folder, and return where. Throws with
 *  the backend's own reason when it refuses, so the person reads what was wrong
 *  rather than that something was. */
export async function saveAppFolder(block: PreviewableBlock): Promise<string> {
  const titled = /<title[^>]*>([\s\S]*?)<\/title>/i.exec(block.code);
  const response = await fetch(`${import.meta.env.VITE_ZARAM_API ?? ''}/apps/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: titled?.[1]?.trim() || 'app',
      files: (block.files ?? []).map((f) => ({ path: f.path, content: f.code })),
    }),
  });
  if (!response.ok) {
    let reason = `the save failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') reason = body.detail;
    } catch {
      /* the status is the reason */
    }
    throw new Error(reason);
  }
  return String(((await response.json()) as { path?: string }).path ?? '');
}
