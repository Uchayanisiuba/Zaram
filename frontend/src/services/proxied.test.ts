/**
 * Every path a service client calls is proxied to the backend in dev.
 *
 * This has already gone wrong once, and it went wrong quietly: `/projects` was
 * added to the backend and to a client and never to the Vite proxy, so every
 * call from the frontend hit the dev server instead — which answers, with
 * `index.html`, so there is no network error to notice. It was found by opening
 * the app and looking, which is not a way to find the next one.
 *
 * The check is deliberately dumb: read the literal paths out of the clients,
 * read the proxy keys out of the config, and require a prefix match. It cannot
 * see a path built at runtime, and it does not try — what it guards is the
 * ordinary case of adding an endpoint and forgetting one file.
 *
 * Read through Vite's `?raw` and `import.meta.glob` rather than `node:fs`, for
 * the reason `index-html.test.ts` gives: the frontend has no `@types/node` and
 * `tsc --noEmit` is one of the gates. A test that fails typecheck is not
 * cheaper than the bug.
 */
import { describe, it, expect } from 'vitest';

import viteConfig from '../../vite.config.js?raw';

//: Every client in this directory, as source text.
const CLIENT_SOURCES = import.meta.glob('./*.ts', {
  query: '?raw',
  eager: true,
  import: 'default',
}) as Record<string, string>;

/** The top-level segment of every proxy rule, e.g. "/egress". */
function proxiedPrefixes(): string[] {
  const proxyBlock = viteConfig.slice(viteConfig.indexOf('proxy: {'));
  return [...proxyBlock.matchAll(/'(\/[a-z0-9_-]+)':\s*\{\s*target/gi)].map((m) => m[1]);
}

/** Paths the clients ask for, as literals: `${API_BASE}/egress/policy`. */
function requestedPaths(): { file: string; path: string }[] {
  const found: { file: string; path: string }[] = [];

  for (const [file, source] of Object.entries(CLIENT_SOURCES)) {
    if (file.endsWith('.test.ts')) continue;
    for (const match of source.matchAll(/\$\{API_BASE\}(\/[a-z0-9_/-]+)/gi)) {
      found.push({ file, path: match[1] });
    }
  }
  return found;
}

describe('the dev proxy', () => {
  it('has a rule for every path the service clients request', () => {
    const prefixes = proxiedPrefixes();
    expect(prefixes.length, 'no proxy rules were parsed out of vite.config.js').toBeGreaterThan(0);

    const requested = requestedPaths();
    expect(requested.length, 'no request paths were parsed out of the clients').toBeGreaterThan(0);

    const unproxied = requested.filter(
      ({ path }) => !prefixes.some((prefix) => path === prefix || path.startsWith(`${prefix}/`)),
    );

    expect(
      unproxied,
      `not in vite.config.js proxy: ${unproxied.map((u) => `${u.path} (${u.file})`).join(', ')}`,
    ).toEqual([]);
  });
});
