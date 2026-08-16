/**
 * Every backend route prefix is proxied — by **both** origins the frontend is
 * ever served from.
 *
 * Why this is a build check and not a test
 * ----------------------------------------
 * A missing prefix does not produce a 404. Both servers fall through to the
 * SPA handler and answer with `index.html` and a **200**, so the client hands
 * HTML to `response.json()` and reports a syntax error at character 0 — a
 * message naming neither the route that failed nor the proxy that swallowed
 * it. An hour to diagnose, one line to fix: the worst ratio a defect can have.
 *
 * It is invisible to every other check here. Unit tests mock `fetch` and the
 * backend's own tests never touch either server.
 *
 * **The premise this file used to carry was false, and it cost eleven routes.**
 * It read: "the packaged build does not use the proxy at all — so this fails
 * only in development". `electron/main.js` hands
 * `config.renderer.apiProxyPrefixes` to `createStaticServer`, which proxies
 * exactly as Vite does. That list had ten prefixes against the dev map's
 * twenty-one, so `/egress`, `/artifacts`, `/providers`, `/export`,
 * `/character`, `/routing` and `/projects` answered 200-with-a-document in
 * every packaged build and were correct in every development one. The egress
 * log and the exporter — rules 3 and 7 — were unreachable in the only build a
 * stranger ever runs. Measured against the built app, not inferred.
 *
 * So the direction of the failure is the opposite of what was written here:
 * development is the environment with the *complete* list, and it is the one
 * environment where being complete does not matter.
 *
 * How the lists are built
 * -----------------------
 * From source, not from a running server. A check that needs the backend up is
 * a check that gets skipped, and this runs in the same breath as `vite build`
 * on a machine with nothing else started.
 *
 *   backend  — `@app.<method>("/path")` in `main.py`, plus the `prefix=` of any
 *              `APIRouter` whose module `main.py` passes to `include_router`.
 *   dev      — the keys of the `proxy` object in `vite.config.js`.
 *   packaged — `apiProxyPrefixes` in `electron/config.js`.
 *
 * All read with regular expressions rather than parsed. That is a real
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
const DESKTOP_CONFIG = path.join(REPO, 'electron', 'config.js');

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

/** `apiProxyPrefixes` in the desktop config — what the packaged origin forwards. */
const packagedPrefixes = () => {
  const source = readFileSync(DESKTOP_CONFIG, 'utf8');
  const start = source.indexOf('apiProxyPrefixes');
  if (start === -1) return new Set();
  const block = source.slice(start, source.indexOf(']', start));
  return new Set([...block.matchAll(/["'](\/[\w-]+)["']/g)].map(([, p]) => p));
};

const backend = backendPrefixes();

/**
 * Both consumers, each with the consequence of getting it wrong.
 *
 * The consequence text is not decoration. The dev failure and the packaged
 * failure are byte-identical from the client's chair — a 200 and a document —
 * and the only thing that tells someone which server ate their request is
 * which file this names.
 */
const consumers = [
  {
    what: 'the dev server',
    file: CONFIG,
    have: proxiedPrefixes(),
    consequence:
      "Vite answers with index.html and a 200, and the client reports a JSON\n" +
      '  parse error naming neither the route nor the proxy.',
  },
  {
    what: 'the packaged app',
    file: DESKTOP_CONFIG,
    have: packagedPrefixes(),
    consequence:
      '`createStaticServer` serves index.html with a 200 for anything it does\n' +
      '  not recognise. This breaks only in a build — never on the machine of\n' +
      '  whoever adds the route.',
  },
];

let failed = false;
for (const { what, file, have, consequence } of consumers) {
  const missing = [...backend].filter((prefix) => !have.has(prefix)).sort();
  if (missing.length === 0) continue;
  failed = true;
  console.error(`\nThese backend prefixes are not proxied by ${what}:\n`);
  for (const prefix of missing) console.error(`  ${prefix}`);
  console.error(`\n  ${consequence}`);
  console.error(`  Add each to ${path.relative(REPO, file)}.\n`);
}

if (failed) process.exit(1);

console.log(
  `proxy covers all ${backend.size} backend prefixes, in development and packaged`,
);
