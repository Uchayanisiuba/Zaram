/**
 * Every backend route prefix is proxied by the dev server.
 *
 * Why this is a build check and not a test
 * ----------------------------------------
 * A prefix missing from `vite.config.js`'s proxy map does not produce a 404.
 * Vite falls through to its SPA handler and answers with `index.html` and a
 * **200**, so the client hands HTML to `response.json()` and reports a syntax
 * error at character 0 — a message that names neither the route that failed
 * nor the proxy that swallowed it. It is an hour to diagnose and one line to
 * fix, which is the worst ratio a defect can have.
 *
 * It is also invisible to every other guard here. Unit tests mock `fetch`, the
 * backend's own tests never touch Vite, and the packaged build does not use the
 * proxy at all — so this fails **only** in development, which is the one place
 * nobody has a check.
 *
 * How the two lists are built
 * ---------------------------
 * From source, not from a running server. A check that needs the backend up is
 * a check that gets skipped, and this has to run in the same breath as
 * `vite build` on a machine with nothing else started.
 *
 *   backend  — `@app.<method>("/path")` in `main.py`, plus the `prefix=` of any
 *              `APIRouter` whose module `main.py` passes to `include_router`.
 *   frontend — the keys of the `proxy` object in `vite.config.js`.
 *
 * Both are read with regular expressions rather than parsed. That is a real
 * limitation and it fails in the safe direction: an unusual spelling is not
 * matched, so it is not required, so this reports nothing rather than
 * something wrong. A prefix that has to be added by hand is a comment in the
 * config, not a false failure in the build.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, '../..');
const MAIN = path.join(REPO, 'backend', 'main.py');
const CONFIG = path.join(REPO, 'frontend', 'vite.config.js');

/** Paths the frontend is not expected to reach through the proxy.
 *
 *  `/openapi.json`, `/docs` and `/redoc` are FastAPI's own and are opened
 *  directly in a browser against port 8420 when they are wanted at all. */
const NOT_PROXIED = new Set(['/openapi.json', '/docs', '/redoc']);

/** The first path segment — the granularity the proxy map works at. */
const prefixOf = (route) => {
  const [, head] = route.split('/');
  return head ? `/${head}` : '/';
};

const backendPrefixes = () => {
  const main = readFileSync(MAIN, 'utf8');
  const found = new Set();

  for (const [, route] of main.matchAll(
    /@app\.(?:get|post|put|delete|patch)\(\s*["']([^"']+)["']/g,
  )) {
    if (!NOT_PROXIED.has(route)) found.add(prefixOf(route));
  }

  // Included routers contribute their prefix rather than their paths. Which
  // modules those are is read from `main.py` too, so adding a router without
  // proxying it fails here rather than in somebody's afternoon.
  const included = [...main.matchAll(/from\s+([\w.]+)\s+import\s+router\s+as\s+(\w+)/g)];
  for (const [, module] of included) {
    const file = path.join(REPO, 'backend', ...module.split('.')) + '.py';
    let source;
    try {
      source = readFileSync(file, 'utf8');
    } catch {
      continue; // Not a file we can read is not a failure — see the header.
    }
    for (const [, prefix] of source.matchAll(/APIRouter\([^)]*prefix\s*=\s*["']([^"']+)["']/g)) {
      found.add(prefixOf(prefix));
    }
  }

  return found;
};

const proxiedPrefixes = () => {
  const config = readFileSync(CONFIG, 'utf8');
  const block = config.slice(config.indexOf('proxy:'));
  return new Set([...block.matchAll(/["'](\/[\w-]+)["']\s*:\s*\{/g)].map(([, p]) => p));
};

const backend = backendPrefixes();
const proxied = proxiedPrefixes();
const missing = [...backend].filter((prefix) => !proxied.has(prefix)).sort();

if (missing.length > 0) {
  console.error('\nThese backend prefixes are not proxied by the dev server:\n');
  for (const prefix of missing) console.error(`  ${prefix}`);
  console.error(
    '\nIn development the request will return Vite\'s index.html with a 200,' +
      '\nand the client will report a JSON parse error naming neither.' +
      `\nAdd each to the proxy map in ${path.relative(REPO, CONFIG)}.\n`,
  );
  process.exit(1);
}

console.log(`proxy covers all ${backend.size} backend prefixes`);
