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
 *  network, no navigation, no popups, no modals. The consequence is that
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
  function send(kind, detail) {
    try { parent.postMessage({ __zaramPreview: true, kind: kind, detail: String(detail) }, '*'); }
    catch (e) { /* nothing to be done from in here */ }
  }
  window.addEventListener('error', function (e) {
    send('error', (e && e.message) || 'script error');
  });
  window.addEventListener('unhandledrejection', function (e) {
    send('error', (e && e.reason && e.reason.message) || 'unhandled rejection');
  });
  document.addEventListener('securitypolicyviolation', function (e) {
    send('blocked', (e.violatedDirective || 'policy') + ' blocked ' + (e.blockedURI || 'inline'));
  });
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
  // The reporter goes before the page so it is listening while the page's own
  // script runs — registered afterwards it would miss the very errors that
  // matter, which are the ones thrown during setup.
  return APP_CSP + FRAME_STYLE + ERROR_REPORTER + source;
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
