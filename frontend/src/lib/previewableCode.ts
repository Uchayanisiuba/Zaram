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
export const APP_CSP =
  "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; " +
  "script-src 'unsafe-inline' 'unsafe-eval'; style-src 'unsafe-inline'; " +
  "img-src data:; font-src data:;\">";

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

/** The sandbox the app frame runs under.
 *
 *  **`allow-same-origin` must never join this list.** Granted alongside
 *  `allow-scripts` it does not merely widen the sandbox, it dissolves it: the
 *  frame would share this app's origin and could reach in and remove its own
 *  `sandbox` attribute. The two together are the documented footgun, and
 *  `previewableCode.test.ts` asserts against it directly rather than trusting
 *  a comment to be read. */
export const APP_SANDBOX = 'allow-scripts';

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
export function wrapForPreview(source: string, mode: 'document' | 'app' = 'document'): string {
  if (mode !== 'app') return DOCUMENT_CSP + FRAME_STYLE + source;
  // Three things ahead of the page, and the order of all three is load-bearing.
  // The reporter is first so it is listening while everything after it runs —
  // registered later it would miss the errors that matter most, which are the
  // ones thrown during setup, and it would not be able to report a shim that
  // failed to install. The shim is next because it has to be in place before
  // the page's *first* line: the storage read that broke Tetris was line one.
  return APP_CSP + FRAME_STYLE + ERROR_REPORTER + SEALED_STORAGE + source;
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
  /** The block's contents, verbatim. */
  code: string;
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
export function savePreviewable(block: PreviewableBlock): void {
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
}
