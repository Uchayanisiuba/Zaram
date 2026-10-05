import { describe, it, expect } from 'vitest';
import {
  appCsp,
  extractPreviewable,
  filenameFor,
  savePreviewable,
  wrapForPreview,
  APP_CSP,
  APP_SANDBOX,
  findStuckLoop,
  DOCUMENT_CSP,
  ERROR_REPORTER,
  SEALED_STORAGE,
} from './previewableCode';

describe('extractPreviewable', () => {
  it('finds an html block and returns its contents verbatim', () => {
    const reply = 'Here is the page:\n\n```html\n<h1>Hello</h1>\n```\n\nLet me know.';
    const block = extractPreviewable(reply);
    expect(block?.language).toBe('html');
    expect(block?.label).toBe('HTML');
    expect(block?.code).toContain('<h1>Hello</h1>');
  });

  it('finds svg too', () => {
    const block = extractPreviewable('```svg\n<svg viewBox="0 0 1 1"></svg>\n```');
    expect(block?.label).toBe('SVG');
  });

  it('returns null for a reply with no code at all', () => {
    expect(extractPreviewable('Just prose, no fences here.')).toBeNull();
  });

  /** The offer must never come to mean "run this". Executing model-written
   *  code is the mutative tier, which is out of scope until undo, confirm and
   *  sandbox exist — so a language we cannot merely *render* is not offered. */
  it('refuses languages that would have to be executed rather than rendered', () => {
    expect(extractPreviewable('```python\nprint("hi")\n```')).toBeNull();
    expect(extractPreviewable('```bash\nrm -rf /\n```')).toBeNull();
    expect(extractPreviewable('```js\nalert(1)\n```')).toBeNull();
  });

  /** This runs against text that is still streaming, so the button has to
   *  appear when the code does rather than a beat after the closing fence. */
  it('returns a block whose fence has not closed yet', () => {
    const block = extractPreviewable('```html\n<main>partial');
    expect(block?.code).toContain('<main>partial');
  });

  it('skips a non-previewable block to find a previewable one after it', () => {
    const reply = '```python\nx = 1\n```\n\n```html\n<p>page</p>\n```';
    expect(extractPreviewable(reply)?.language).toBe('html');
  });

  it('ignores an empty fence rather than opening a blank panel', () => {
    expect(extractPreviewable('```html\n\n```')).toBeNull();
  });

  it('tolerates extra words on the fence line', () => {
    expect(extractPreviewable('```html title=page\n<p>x</p>\n```')?.language).toBe('html');
  });
});

describe('wrapForPreview', () => {
  /** The policy has to be in force before anything the document declares, and
   *  a generated page carrying its own meta cannot loosen ours — the more
   *  restrictive of two policies wins by specification. */
  it('puts the policy ahead of the document', () => {
    expect(wrapForPreview('<p>hi</p>').indexOf(DOCUMENT_CSP)).toBe(0);
    expect(wrapForPreview('<p>hi</p>', 'app').indexOf(APP_CSP)).toBe(0);
    expect(wrapForPreview('<p>hi</p>')).toContain('<p>hi</p>');
  });

  it('defaults to the document policy, so a generated invoice runs nothing', () => {
    expect(wrapForPreview('<p>hi</p>')).toContain(DOCUMENT_CSP);
    expect(DOCUMENT_CSP).not.toContain('script-src');
  });

  it('gives a page from a reply its script, and only that', () => {
    expect(APP_CSP).toContain("script-src 'unsafe-inline'");
    expect(APP_CSP).toContain("default-src 'none'");
  });
});

describe('the seal on an app preview', () => {
  /** `default-src 'none'` covers `connect-src`, so a script may compute and
   *  may not phone anywhere. This is the clause that keeps a running page out
   *  of the egressive tier — a beacon from inside the frame is a request
   *  `EgressGate` could never see, because that intercepts what the *backend*
   *  sends. */
  it('permits no network from either policy', () => {
    for (const policy of [DOCUMENT_CSP, APP_CSP]) {
      expect(policy).toContain("default-src 'none'");
      expect(policy).not.toContain('connect-src');
      expect(policy).not.toContain('https:');
      expect(policy).not.toContain('http:');
      expect(policy).not.toContain('*');
    }
  });

  /** The documented footgun, asserted rather than commented. `allow-scripts`
   *  together with `allow-same-origin` does not widen the sandbox — it
   *  dissolves it, because the frame then shares this app's origin and can
   *  reach in and strip its own sandbox attribute. */
  it('never grants same-origin beside scripts', () => {
    expect(APP_SANDBOX).toContain('allow-scripts');
    expect(APP_SANDBOX).not.toContain('allow-same-origin');
  });

  /** Each of these is a capability nobody asked for and every one of them is
   *  a route back out of the frame. Listed individually so adding one has to
   *  be a deliberate edit here rather than a quiet widening there. */
  it('grants nothing that could leave the frame', () => {
    for (const capability of [
      'allow-same-origin',
      'allow-top-navigation',
      'allow-popups',
      'allow-modals',
      'allow-downloads',
      'allow-forms',
    ]) {
      expect(APP_SANDBOX).not.toContain(capability);
    }
  });

  /** Granted deliberately. Inline script is already permitted, so a page here
   *  can run anything with or without it — withholding `eval` took nothing
   *  from an attacker and broke every generated calculator that parses its
   *  expression with it. The document policy still refuses both. */
  it('grants eval to an app and neither script capability to a document', () => {
    expect(APP_CSP).toContain('unsafe-eval');
    expect(DOCUMENT_CSP).not.toContain('unsafe-eval');
    expect(DOCUMENT_CSP).not.toContain('unsafe-inline; script');
  });

  /** A silent preview is the failure mode that cost two rounds of guessing.
   *  The reporter is what turns "the buttons do nothing" into a sentence. */
  it('injects the fault reporter ahead of the page, and only for an app', () => {
    const wrapped = wrapForPreview('<p id="page">x</p>', 'app');
    expect(wrapped).toContain('__zaramPreview');
    expect(wrapped.indexOf('__zaramPreview')).toBeLessThan(wrapped.indexOf('id="page"'));
    expect(wrapForPreview('<p>x</p>')).not.toContain('__zaramPreview');
  });

  it('reports a policy refusal, which is the failure nobody can otherwise see', () => {
    expect(ERROR_REPORTER).toContain('securitypolicyviolation');
    expect(ERROR_REPORTER).toContain('unhandledrejection');
  });

  /** The directive alone cannot produce a sentence a person can read. "the
   *  page asked cdn.tailwindcss.com for part of itself" needs the host, and
   *  the panel has no other way to get it — it cannot see into an opaque
   *  origin. Reported as a field rather than parsed back out of the prose. */
  it('carries the host a refusal named, not only the directive', () => {
    expect(ERROR_REPORTER).toContain('e.blockedURI');
    expect(ERROR_REPORTER).toContain('uri:');
  });
});

describe('storage a generated page can actually use', () => {
  /** The bug the shim exists for, and it is why a working Tetris looked
   *  broken. In an opaque origin `localStorage` does not return an empty
   *  store — it *throws* `SecurityError` on the first read. A generated game
   *  opens with `parseInt(localStorage.getItem('highScore') || '0')`, that
   *  line throws at the top level, and nothing after it runs: the canvas
   *  stays black and no key does anything. A portfolio page hits the same
   *  wall reading a saved theme, which is why both symptoms arrived together.
   *
   *  Measured in a real sandboxed frame either side of the change — before,
   *  the reporter caught "Uncaught SecurityError: Failed to read the
   *  'localStorage' property from 'Window'"; after, the game runs. */
  it('hands an app frame its own storage, ahead of the page', () => {
    const wrapped = wrapForPreview('<p id="page">x</p>', 'app');
    expect(wrapped).toContain(SEALED_STORAGE);
    expect(wrapped.indexOf(SEALED_STORAGE)).toBeLessThan(wrapped.indexOf('id="page"'));
  });

  it('shims every store that throws in an opaque origin', () => {
    for (const name of ['localStorage', 'sessionStorage', 'cookie']) {
      expect(SEALED_STORAGE).toContain(name);
    }
  });

  /** Left alone deliberately. `indexedDB.open` throws the same
   *  `SecurityError`, and a half-built fake database would fail later,
   *  deeper and less legibly than the honest error the reporter already
   *  carries. */
  it('fakes no database, because a bad one fails less legibly than none', () => {
    expect(SEALED_STORAGE).not.toContain('indexedDB');
  });

  /** The shim has to be strictly *less* than real storage, which is the whole
   *  reason it does not widen the seal: real `localStorage` would be wrong
   *  here because it would be Zaram's own origin persisting across previews,
   *  and a map inside the frame persists across nothing. Nothing in it may
   *  reach a disk, a parent, or a network. */
  it('is a map inside the frame and reaches nothing outside it', () => {
    for (const reach of ['fetch(', 'XMLHttpRequest', 'WebSocket', 'parent.', 'top.', 'http']) {
      expect(SEALED_STORAGE).not.toContain(reach);
    }
  });

  it('gives a document none of it, because a document runs no script at all', () => {
    expect(wrapForPreview('<p>x</p>')).not.toContain(SEALED_STORAGE);
  });
});

describe('saving a page written in a reply', () => {
  const block = (code: string, language = 'html') => ({
    language,
    label: language.toUpperCase(),
    code,
  });

  it("names the file from the page's own title", () => {
    expect(filenameFor(block('<title>Budget Calculator</title><p>x</p>'))).toBe(
      'budget-calculator.html',
    );
  });

  it('falls back to a dull name rather than an unreadable unique one', () => {
    expect(filenameFor(block('<p>no title here</p>'))).toBe('page.html');
    expect(filenameFor(block('<circle r="4"/>', 'svg'))).toBe('image.svg');
  });

  it('keeps a filename to characters three operating systems agree on', () => {
    const name = filenameFor(block('<title>Q3 / Q4: "spend" report *draft*</title>'));
    expect(name).toBe('q3-q4-spend-report-draft.html');
  });

  /** The regression worth having a test for: the preview wraps the page in our
   *  CSP, our stylesheet and a `postMessage` reporter, and none of that is the
   *  user's document. Saving the framed version would hand them a file with a
   *  policy meta tag they did not write and a call to a parent frame that does
   *  not exist. */
  it('writes the markup the model wrote, not what the preview frame runs', async () => {
    const source = '<title>T</title><p>body</p>';
    const blobs: Blob[] = [];
    const originalCreate = URL.createObjectURL;
    const originalRevoke = URL.revokeObjectURL;
    URL.createObjectURL = ((given: Blob) => {
      blobs.push(given);
      return 'blob:stub';
    }) as typeof URL.createObjectURL;
    URL.revokeObjectURL = (() => {}) as typeof URL.revokeObjectURL;
    try {
      savePreviewable(block(source));
      expect(blobs).toHaveLength(1);
      const written = await blobs[0].text();
      expect(written).toBe(source);
      expect(written).not.toContain('Content-Security-Policy');
      expect(written).not.toContain('__zaramPreview');
      expect(blobs[0].type).toContain('text/html');
    } finally {
      URL.createObjectURL = originalCreate;
      URL.revokeObjectURL = originalRevoke;
    }
  });

  it('leaves no anchor behind in the document', () => {
    const originalCreate = URL.createObjectURL;
    const originalRevoke = URL.revokeObjectURL;
    URL.createObjectURL = (() => 'blob:stub') as typeof URL.createObjectURL;
    URL.revokeObjectURL = (() => {}) as typeof URL.revokeObjectURL;
    try {
      savePreviewable(block('<p>x</p>'));
      expect(document.querySelectorAll('a[download]')).toHaveLength(0);
    } finally {
      URL.createObjectURL = originalCreate;
      URL.revokeObjectURL = originalRevoke;
    }
  });
});

describe('letting a preview load a library', () => {
  /**
   * Asked for 4 October 2026: Zaram should be able to preview Three.js.
   * A page saying `<script src="https://cdn.jsdelivr.net/npm/three">`
   * rendered as a black rectangle, because `default-src 'none'` refuses
   * every remote sub-resource — correctly, since such a request carries
   * the user's IP and `EgressGate` cannot see it.
   *
   * The fix is not a looser policy. It is rule 5: default deny, then an
   * explicit per-item decision, per host and per preview.
   */
  it('still refuses everything by default', () => {
    // The property that must not drift. Called with nothing, this is the
    // policy every preview starts under.
    expect(appCsp()).toBe(APP_CSP);
    expect(appCsp()).toContain("default-src 'none'");
    expect(appCsp()).not.toContain('https://');
  });

  it('names an allowed host in script-src', () => {
    const csp = appCsp(['cdn.jsdelivr.net']);
    expect(csp).toMatch(/script-src[^;]*https:\/\/cdn\.jsdelivr\.net/);
  });

  it('lets it supply styles, fonts and images too', () => {
    // A library that loads is no use if its stylesheet does not. These are
    // the same grant: the person allowed that host to supply part of the
    // page.
    const csp = appCsp(['cdn.jsdelivr.net']);
    for (const directive of [/style-src[^;]*jsdelivr/, /font-src[^;]*jsdelivr/, /img-src[^;]*jsdelivr/]) {
      expect(csp).toMatch(directive);
    }
  });

  it('does not let the page talk back', () => {
    // `connect-src` falls to `default-src 'none'` and stays there. A
    // library fetched by `<script src>` is a thing the person agreed to
    // load; `fetch()` to the same host is the page talking, which is a
    // different act and was not what was allowed.
    const csp = appCsp(['cdn.jsdelivr.net']);
    expect(csp).not.toContain('connect-src');
    expect(csp).toContain("default-src 'none'");
  });

  it('refuses a host that is not a hostname', () => {
    // The host arrives from a CSP violation report, which is text the
    // *page* influenced. A page that could write `*` into the policy
    // would have talked its way out of the sandbox.
    // Asserted as *the policy is unchanged*, not as "the string is
    // absent". `data:` is already legitimately in `img-src` and
    // `font-src`, so absence is the wrong property — it fails on the one
    // input that matters and passes for the wrong reason on the rest.
    for (const nasty of ['*', "' 'unsafe-inline", 'foo.com; script-src *', 'data:', '', '  ']) {
      expect(appCsp([nasty])).toBe(APP_CSP);
    }
  });

  it('refuses a bare word, which cannot be a CDN', () => {
    expect(appCsp(['localhost'])).toBe(APP_CSP);
  });

  it('is bounded, so a page cannot grow the policy without limit', () => {
    const many = Array.from({ length: 40 }, (_, i) => `h${i}.example.com`);
    const csp = appCsp(many);
    expect((csp.match(/https:\/\//g) ?? []).length).toBeLessThanOrEqual(8 * 4);
  });

  it('a document never gets the allowance, however it is called', () => {
    // An invoice has no reason to reach anywhere, and granting it one
    // would be surface bought for nothing.
    const wrapped = wrapForPreview('<p>hi</p>', 'document', ['cdn.jsdelivr.net']);
    expect(wrapped).not.toContain('jsdelivr');
    expect(wrapped).toContain(DOCUMENT_CSP);
  });

  it('an app preview with no allowance is unchanged', () => {
    expect(wrapForPreview('<p>hi</p>', 'app')).toContain(APP_CSP);
  });

  it('an app preview with one carries it', () => {
    expect(wrapForPreview('<p>hi</p>', 'app', ['cdn.jsdelivr.net'])).toContain('jsdelivr');
  });
});

// ------------------------------------------------------------------ playback
//
// "Playback and review on the HTML surface" (4 October 2026). The frame is
// sealed with an opaque origin, so the panel cannot reach in to pause a page;
// the page is handed a listener instead. These run the injected script against
// a fake window and watch it hold and release callbacks, because "it contains
// the word requestAnimationFrame" is not evidence a game stops.

import { PLAYBACK } from './previewableCode';

interface Held {
  callback: (arg?: unknown) => void;
}

function fakeWindow() {
  const raf: Held[] = [];
  const timeouts: Held[] = [];
  const intervals: Held[] = [];
  const listeners: Record<string, Array<(e: unknown) => void>> = {};
  const parentMessages: unknown[] = [];
  const appended: Array<{ textContent: string }> = [];
  const parent = { postMessage: (m: unknown) => parentMessages.push(m) };

  const win: Record<string, unknown> = {
    parent,
    document: {
      createElement: () => ({ textContent: '', parentNode: null }),
      head: {
        appendChild: (el: { textContent: string; parentNode: unknown }) => {
          appended.push(el);
          el.parentNode = { removeChild: (e: unknown) => appended.splice(appended.indexOf(e as never), 1) };
        },
      },
      documentElement: {},
    },
    requestAnimationFrame: (cb: Held['callback']) => (raf.push({ callback: cb }), raf.length),
    setTimeout: (cb: Held['callback']) => (timeouts.push({ callback: cb }), timeouts.length),
    setInterval: (cb: Held['callback']) => (intervals.push({ callback: cb }), intervals.length),
    addEventListener: (type: string, fn: (e: unknown) => void) => {
      (listeners[type] ||= []).push(fn);
    },
  };

  // Run the script exactly as the frame would, with this window as `window`.
  const body = PLAYBACK.replace(/^<script>/, '').replace(/<\/script>$/, '');
  new Function('window', body)(win);

  const send = (data: unknown, from: unknown = parent) =>
    listeners.message?.forEach((fn) => fn({ source: from, data }));
  const control = (action: string, from: unknown = parent) =>
    send({ __zaramPreviewControl: true, action }, from);
  const tick = (list: Held[], arg?: unknown) => list.splice(0).forEach((h) => h.callback(arg));

  return { win, raf, timeouts, intervals, parentMessages, appended, send, control, tick };
}

type Raf = (cb: (t: number) => void) => number;
type Timeout = (cb: (...a: unknown[]) => void, ms: number, ...a: unknown[]) => number;

describe('playback: pausing a page that moves', () => {
  it('is injected for an app and never for a document', () => {
    expect(wrapForPreview('<p>x</p>', 'app')).toContain(PLAYBACK);
    expect(wrapForPreview('<p>x</p>')).not.toContain(PLAYBACK);
  });

  it('is in place before the page’s first line', () => {
    const wrapped = wrapForPreview('<p id="page">x</p>', 'app');
    expect(wrapped.indexOf(PLAYBACK)).toBeLessThan(wrapped.indexOf('id="page"'));
  });

  it('closes its script tag the way the other preludes do, so it cannot end the document', () => {
    expect(PLAYBACK.endsWith('</script>')).toBe(true);
    expect(PLAYBACK.slice(0, -9)).not.toContain('</script>');
  });

  it('lets a running page run: nothing is held until it is told to pause', () => {
    const f = fakeWindow();
    const ran: number[] = [];
    (f.win.requestAnimationFrame as Raf)((t) => ran.push(t));
    f.tick(f.raf, 16);
    expect(ran).toEqual([16]);
  });

  it('holds an animation frame while paused, and runs it when resumed', () => {
    const f = fakeWindow();
    const ran: number[] = [];
    (f.win.requestAnimationFrame as Raf)((t) => ran.push(t));
    f.control('pause');
    f.tick(f.raf, 16);
    expect(ran).toEqual([]); // held, not run and not dropped
    f.control('play');
    expect(ran).toEqual([16]); // released
  });

  it('holds a timeout while paused and runs it on resume', () => {
    const f = fakeWindow();
    let fired = 0;
    (f.win.setTimeout as Timeout)(() => (fired += 1), 100);
    f.control('pause');
    f.tick(f.timeouts);
    expect(fired).toBe(0);
    f.control('play');
    expect(fired).toBe(1);
  });

  it('passes a timeout its extra arguments', () => {
    const f = fakeWindow();
    const got: unknown[] = [];
    (f.win.setTimeout as Timeout)((...a) => got.push(...a), 10, 'x', 'y');
    f.tick(f.timeouts);
    expect(got).toEqual(['x', 'y']);
  });

  it('holds one tick of an interval however many were missed, so a paused game does not lurch', () => {
    const f = fakeWindow();
    let fired = 0;
    (f.win.setInterval as Timeout)(() => (fired += 1), 16);
    f.control('pause');
    for (let i = 0; i < 50; i += 1) f.intervals[0].callback();
    expect(fired).toBe(0);
    f.control('play');
    expect(fired).toBe(1);
  });

  it('resumes an interval that carries on afterwards', () => {
    const f = fakeWindow();
    let fired = 0;
    (f.win.setInterval as Timeout)(() => (fired += 1), 16);
    f.control('pause');
    f.intervals[0].callback();
    f.control('play');
    f.intervals[0].callback();
    expect(fired).toBe(2);
  });

  it('stops CSS animations with a rule, and removes it on resume', () => {
    const f = fakeWindow();
    f.control('pause');
    expect(f.appended).toHaveLength(1);
    expect(f.appended[0].textContent).toContain('animation-play-state: paused');
    f.control('play');
    expect(f.appended).toHaveLength(0);
  });

  it('does nothing twice: pausing a paused page adds no second rule', () => {
    const f = fakeWindow();
    f.control('pause');
    f.control('pause');
    expect(f.appended).toHaveLength(1);
  });

  it('takes orders only from its parent', () => {
    const f = fakeWindow();
    const ran: number[] = [];
    (f.win.requestAnimationFrame as Raf)((t) => ran.push(t));
    f.control('pause', { someone: 'else' });
    f.tick(f.raf, 1);
    expect(ran).toEqual([1]); // not paused by a stranger
  });

  it('ignores a message that is not a playback control', () => {
    const f = fakeWindow();
    const ran: number[] = [];
    (f.win.requestAnimationFrame as Raf)((t) => ran.push(t));
    f.send({ action: 'pause' }); // from the parent, but not flagged as a control
    f.send('pause');
    f.send(null);
    f.tick(f.raf, 2);
    expect(ran).toEqual([2]);
  });

  it('reports a callback that throws on resume, rather than swallowing it', () => {
    const f = fakeWindow();
    (f.win.setTimeout as Timeout)(() => {
      throw new Error('boom');
    }, 1);
    f.control('pause');
    f.tick(f.timeouts);
    f.control('play');
    expect(f.parentMessages).toContainEqual(
      expect.objectContaining({ __zaramPreview: true, kind: 'error', detail: 'boom' }),
    );
  });

  it('reaches nothing outside the frame', () => {
    for (const reach of ['fetch(', 'XMLHttpRequest', 'WebSocket', 'http', 'top.', 'localStorage']) {
      expect(PLAYBACK).not.toContain(reach);
    }
  });
});

describe('a loop that cannot end is found before it runs — 5 October 2026', () => {
  // The resident model wrote this 23 times in one page; the page froze before
  // it drew anything, and a frozen frame can take the window with it.
  it('finds the missing increment, with its line', () => {
    const page = '<script>\nconst a = 1;\nfunction f(){ for(let i=0;i<16;i)for(let j=0;j<16;j++){ g(i,j); } }\n</script>';
    expect(findStuckLoop(page)).toEqual({ line: 3, text: 'for(let i=0;i<16;i)' });
  });

  it('finds it with spaces, var, and no declaration keyword', () => {
    expect(findStuckLoop('for ( var n = 0 ; n < 5 ; n ) { }')).not.toBeNull();
    expect(findStuckLoop('for (k = 0; k < 5; k) {}')).not.toBeNull();
  });

  it.each([
    'for(let i=0;i<16;i++){}',
    'for(let i=0;i<16;i+=2){}',
    'for(let i=16;i>0;i--){}',
    'for(let i=0;i<16;i=next(i)){}',
    'for(const x of list){}',
    'for(let i=0, j=9; i<j; i++, j--){}',
    'while(true){ if(done) break; }',
    'for(;;){ tick(); }',
    'for(let i=0;i<n;j){}',
  ])('does not flag %s', (code) => {
    expect(findStuckLoop(code)).toBeNull();
  });
});
