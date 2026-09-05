/**
 * Presenting this launch's credential on every request to Zaram's backend.
 *
 * The API refuses callers that cannot — see `backend/core/api_secret.py`. The
 * question here is only how the page gets the value and how it gets attached.
 *
 * **Attached by wrapping `fetch` once, not by each client.**
 * `chatClient`, `settingsClient`, `memoryClient`, `egressClient`,
 * `artifactsClient`, `ingestClient` and `readinessClient` each call `fetch`
 * directly, and the next one will too. A header added per client is a header
 * the eighth client forgets, and the symptom would be a 401 in one corner of
 * the product — which is this repository's single most expensive failure
 * shape, the feature that is complete and tested and cannot happen. One
 * wrapper cannot be forgotten by code that has not been written yet.
 *
 * **Only same-origin requests.** The wrapper must never attach the credential
 * to an outbound URL. Everything the frontend calls on the backend is
 * same-origin — `/chat`, `/memory` — because the dev server proxies and the
 * packaged build is served from the same static server that proxies. So
 * "relative, or this page's origin" is the whole rule, and anything absolute
 * and elsewhere is left exactly as it was. Sending a local credential to a
 * third party would be a rule 3 violation committed by a convenience.
 *
 * **Where the value comes from.** In the desktop app, over IPC from the main
 * process, which minted it. In development there is no main process, so Vite
 * injects the same value it reads from the file the backend writes. Never
 * from a command-line argument: process command lines are readable by other
 * processes on Windows, which is the audience this is for.
 */

/** Resolved once at startup. `null` means no credential was available, which
 *  is a legitimate state in a browser tab opened against a backend that is not
 *  running — the requests then fail with 401, which is the honest answer. */
let credential: string | null = null;

/** `import.meta.env` is replaced at build time. In a packaged build this is
 *  `undefined`, because `vite.config.js` only defines it when serving. */
const FROM_VITE: string | undefined = import.meta.env?.VITE_ZARAM_API_SECRET;

function sameOrigin(input: RequestInfo | URL): boolean {
  try {
    const url = typeof input === 'string'
      ? input
      : input instanceof URL
        ? input.href
        : input.url;
    // A relative URL has no origin of its own and is by definition this one.
    return new URL(url, window.location.href).origin === window.location.origin;
  } catch {
    // An unparseable input is not something to attach a secret to.
    return false;
  }
}

/**
 * Resolve the credential and install the wrapper. Call once, before render.
 *
 * Async because the desktop bridge is IPC. Awaiting it before the first paint
 * is deliberate: a request that raced the resolution would get a 401 and be
 * indistinguishable, in the interface, from a backend that is down.
 */
export async function installApiCredential(): Promise<void> {
  // **The desktop host wins, and the order here is the whole fix.**
  //
  // This used to read `FROM_VITE ?? null` first and consult the bridge only
  // when that was empty. Both are present at once in the case nobody had run
  // — the *real* `electron/main.js` loading the Vite dev server — and they do
  // not agree: `main.js` mints a fresh secret per launch and hands it over
  // IPC, while Vite baked in whatever `backend/api-secret` happened to hold
  // when the dev server booted, which is a file the backend no longer writes
  // once `ZARAM_API_SECRET` is set. The stale one won, every request came back
  // 401, and the interface reported **"Zaram engine not running"** — a backend
  // that was up, healthy, and answering the launcher's own health check 200.
  //
  // The bridge is authoritative because the process on the other end is the
  // one that minted the value. Vite's injection is the fallback for the case
  // it was written for: a browser tab with no desktop host at all.
  const bridge = window.zaram?.app?.getApiSecret;
  if (typeof bridge === 'function') {
    try {
      credential = (await bridge()) || null;
    } catch {
      credential = null;
    }
  }

  if (!credential) credential = FROM_VITE ?? null;

  const original = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    if (!credential || !sameOrigin(input)) return original(input, init);

    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    // `setdefault` semantics: a caller that set it meant it. Nothing does
    // today, and a test that sends a deliberately wrong credential would be
    // silently corrected if this overwrote.
    if (!headers.has('X-Zaram-Auth')) headers.set('X-Zaram-Auth', credential);

    return original(input, { ...init, headers });
  };
}

/** For tests and for the readiness surface, which has a reason to say whether
 *  the interface is able to talk to its own backend at all. */
export function hasApiCredential(): boolean {
  return credential !== null;
}
