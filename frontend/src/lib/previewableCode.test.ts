import { describe, it, expect } from 'vitest';
import {
  extractPreviewable,
  wrapForPreview,
  APP_CSP,
  APP_SANDBOX,
  DOCUMENT_CSP,
  ERROR_REPORTER,
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
});
