/**
 * three.js for the preview, from Zaram's own copy — no network.
 *
 * Asked for 5 October 2026: a "Block World" Minecraft-style page the resident
 * Qwen wrote showed its title screen and nothing else — *"Uncaught
 * ReferenceError: THREE is not defined"* — because the page loads three.js from
 * a CDN and the preview, rightly, has no network. Pressing *Load from
 * cdn.jsdelivr.net* is a working answer and a bad first impression: the most
 * shareable thing a local model can make should play on the first click,
 * offline, with nothing leaving the machine.
 *
 * **What this does.** Zaram already ships three.js — the avatar is drawn with
 * it — so a page that asks a known CDN for three.js, or imports it as a
 * module, is given that copy instead:
 *
 * * a classic `<script src=…three.min.js>` is removed, and `window.THREE` is
 *   defined ahead of the page from the self-contained CommonJS build;
 * * a module import — `from 'three'`, a CDN URL, or the page's own import map
 *   — resolves through an import map to a module that re-exports that same
 *   `window.THREE`, so classic and module code see one copy;
 * * a short, curated list of addons (pointer-lock, orbit and first-person
 *   controls; Perlin and simplex noise) is served the same way, as modules
 *   and as the classic `THREE.PointerLockControls` older pages expect.
 *
 * **What it does not do.** It is one library, the one that makes 3D in a
 * browser possible, not a mirror of npm. Anything else a page asks for still
 * takes the existing path — the frame's fault report names the host and the
 * person can choose to load it. The version is this one (r185) whatever the
 * page asked for; pages written for r128–r160 run on it with, at worst,
 * deprecation warnings, and the panel says which copy was served.
 *
 * Pure functions over text, so the rewriting is testable without loading two
 * megabytes; `loadThree` is the one place that reads the files.
 */

/** The addons served, by their path under `examples/jsm/`. */
export const ADDONS = [
  'controls/PointerLockControls.js',
  'controls/OrbitControls.js',
  'controls/FirstPersonControls.js',
  'math/ImprovedNoise.js',
  'math/SimplexNoise.js',
] as const;

export type AddonPath = (typeof ADDONS)[number];

export interface VendoredThree {
  /** The CommonJS build, verbatim. */
  cjs: string;
  /** Every name three exports, so the module shim can re-export each. */
  names: string[];
  /** Each addon's module source, verbatim. */
  addons: Record<AddonPath, string>;
  /** `r185` — what the panel tells the person was served. */
  revision: string;
}

/** Hosts a page asks for three.js on. A URL elsewhere is left alone. */
const CDN_HOSTS = new Set([
  'cdn.jsdelivr.net',
  'unpkg.com',
  'cdnjs.cloudflare.com',
  'threejs.org',
  'esm.sh',
  'cdn.skypack.dev',
  'ga.jspm.io',
]);

function parsed(spec: string): URL | null {
  try {
    const url = new URL(spec.startsWith('//') ? `https:${spec}` : spec);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url : null;
  } catch {
    return null;
  }
}

/** Is this specifier three.js itself? */
export function isThreeCore(spec: string): boolean {
  if (spec === 'three') return true;
  const url = parsed(spec);
  if (!url || !CDN_HOSTS.has(url.hostname)) return false;
  const segments = url.pathname.split('/').filter(Boolean);
  const last = segments[segments.length - 1] ?? '';
  if (/^three(\.module)?(\.min)?\.js$/.test(last)) return true;
  // esm.sh/three, cdn.skypack.dev/three@0.132.2 — the package, no file.
  return segments.length === 1 && /^three(@[\w.-]+)?$/.test(segments[0]);
}

/** The curated addon a specifier names, or null. Module (`examples/jsm/`,
 *  `three/addons/`) and classic (`examples/js/`) forms both resolve. */
export function addonFor(spec: string): { path: AddonPath; classic: boolean } | null {
  const bare = spec.split(/[?#]/)[0];
  const match = /(?:^three\/addons\/|^three\/examples\/jsm\/|\/examples\/(jsm|js)\/)(.+)$/.exec(bare);
  if (!match) return null;
  if (bare.includes('://') || bare.startsWith('//')) {
    const url = parsed(bare);
    if (!url || !CDN_HOSTS.has(url.hostname)) return null;
  }
  const path = match[2] as AddonPath;
  if (!(ADDONS as readonly string[]).includes(path)) return null;
  return { path, classic: match[1] === 'js' };
}

/** Does this page use three.js in a way this module can serve? */
export function usesThree(source: string): boolean {
  if (/(?:from|import)\s*\(?\s*['"]three['"]/.test(source)) return true;
  if (/"three"\s*:/.test(source) && /type\s*=\s*["']importmap["']/i.test(source)) return true;
  for (const match of source.matchAll(/['"]((?:https?:)?\/\/[^'"\s]+)['"]/g)) {
    if (isThreeCore(match[1])) return true;
  }
  return false;
}

/** Text that is about to sit inside an inline `<script>`. A literal closing
 *  tag would end the element early; none is in r185, and this keeps a later
 *  version from breaking the page silently if one appears. */
function inline(text: string): string {
  return text.replace(/<\/script/gi, '<\\/script');
}

function dataModule(text: string): string {
  return `data:text/javascript;charset=utf-8,${encodeURIComponent(text)}`;
}

/** The classic global, defined once, ahead of the page. A plain object rather
 *  than the frozen exports, because classic addons and older pages assign to
 *  it — `THREE.PointerLockControls = …`. */
function classicThree(cjs: string): string {
  return (
    '<script>(function(){var module={exports:{}};var exports=module.exports;\n' +
    inline(cjs) +
    '\n;window.THREE=Object.assign({},module.exports);})();</script>'
  );
}

/** An addon module, rewritten to read `THREE` and write its classes onto it —
 *  the `examples/js/` shape three stopped shipping in r148. */
export function classicAddon(source: string): string {
  const body = source
    .replace(/import\s*\{([^}]*)\}\s*from\s*['"]three['"];?/g, 'const {$1} = window.THREE;')
    .replace(/export\s*\{([^}]*)\};?/g, (_all, names: string) =>
      names
        .split(',')
        .map((n) => n.trim())
        .filter(Boolean)
        .map((n) => {
          const [local, exported] = n.split(/\s+as\s+/);
          return `window.THREE.${exported ?? local} = ${local};`;
        })
        .join(' '),
    );
  return `<script>(function(){\n${inline(body)}\n})();</script>`;
}

function moduleShim(names: string[]): string {
  // Destructured once from the global, so a module and a classic script in
  // the same page share one copy — two copies of three in one page break
  // `instanceof` across them.
  const safe = names.filter((n) => /^[A-Za-z_$][\w$]*$/.test(n));
  return `const T = window.THREE;\nexport const { ${safe.join(', ')} } = T;\n`;
}

export interface VendoredPage {
  /** Goes ahead of the page, after the frame's own reporter and shims. */
  prefix: string;
  /** The page, with its three.js requests rewritten. */
  body: string;
  /** What was served, in words, for the panel. */
  served: string;
}

/**
 * Rewrite one page to use the local three.js, or `null` when it does not use
 * it. Never throws: a page this cannot make sense of is returned as it came,
 * and the frame's ordinary fault report takes over.
 */
export function vendorPage(source: string, three: VendoredThree, extra = ''): VendoredPage | null {
  // `extra` is the app's other files. Joined into one page, their modules sit
  // inside `data:` URLs where nothing here can read an import, so the caller
  // passes the plain text to be read for them.
  if (!usesThree(source) && !usesThree(extra)) return null;
  try {
    let body = source;

    // 1. Classic tags: the core goes (THREE is defined ahead of the page);
    //    a curated classic addon becomes its inline equivalent in place, so
    //    it still runs after the core and before the page's own script.
    body = body.replace(
      /<script\b[^>]*\bsrc\s*=\s*["']([^"']+)["'][^>]*>\s*<\/script>/gi,
      (tag, src: string) => {
        if (isThreeCore(src)) return '';
        const addon = addonFor(src);
        if (addon) return classicAddon(three.addons[addon.path]);
        return tag;
      },
    );

    // 2. Module specifiers, wherever they are: import statements, dynamic
    //    imports, and the page's own import map.
    const imports: Record<string, string> = {};
    const shim = dataModule(moduleShim(three.names));
    const consider = (spec: string) => {
      if (isThreeCore(spec)) imports[spec] = shim;
      else {
        const addon = addonFor(spec);
        if (addon && !addon.classic) imports[spec] = dataModule(three.addons[addon.path]);
      }
    };
    for (const m of `${body}\n${extra}`.matchAll(/(?:from|import)\s*\(?\s*['"]([^'"]+)['"]/g)) consider(m[1]);
    // An addon imports bare `three`, so it always needs mapping.
    imports.three = shim;

    // 3. One import map. Chromium before 133 honours only the first, so a
    //    page that brought its own has it rewritten in place rather than a
    //    second one added ahead of it.
    let placed = false;
    body = body.replace(
      /(<script\b[^>]*type\s*=\s*["']importmap["'][^>]*>)([\s\S]*?)(<\/script>)/i,
      (all, open: string, json: string, close: string) => {
        try {
          const theirs = JSON.parse(json) as { imports?: Record<string, string> };
          const merged: Record<string, string> = {};
          for (const [key, value] of Object.entries(theirs.imports ?? {})) {
            consider(key);
            consider(value);
            if (isThreeCore(value)) imports[key] = shim;
            // A prefix entry ("three/addons/": "https://…/examples/jsm/") is
            // kept: exact keys outrank it, so anything not curated still
            // falls through to it and is reported like any other host.
            merged[key] = value;
          }
          placed = true;
          return `${open}${JSON.stringify({ ...theirs, imports: { ...merged, ...imports } })}${close}`;
        } catch {
          return all;
        }
      },
    );
    const map = placed ? '' : `<script type="importmap">${JSON.stringify({ imports })}</script>`;

    return {
      prefix: classicThree(three.cjs) + map,
      body,
      served: `three.js ${three.revision}, from Zaram's own copy`,
    };
  } catch {
    return null;
  }
}

let cached: Promise<VendoredThree> | null = null;

/** Read the library once per session. Lazy, so nobody who never previews a
 *  3D page downloads two megabytes of it into the renderer. */
export function loadThree(): Promise<VendoredThree> {
  if (!cached) {
    cached = (async () => {
      const [cjs, lib, ...addons] = await Promise.all([
        // By path: three's package `exports` does not name the CommonJS file
        // as a subpath, only as the `require` condition of the root.
        import('../../node_modules/three/build/three.cjs?raw').then((m) => m.default as string),
        import('three'),
        import('three/examples/jsm/controls/PointerLockControls.js?raw').then((m) => m.default as string),
        import('three/examples/jsm/controls/OrbitControls.js?raw').then((m) => m.default as string),
        import('three/examples/jsm/controls/FirstPersonControls.js?raw').then((m) => m.default as string),
        import('three/examples/jsm/math/ImprovedNoise.js?raw').then((m) => m.default as string),
        import('three/examples/jsm/math/SimplexNoise.js?raw').then((m) => m.default as string),
      ]);
      return {
        cjs,
        names: Object.keys(lib),
        addons: Object.fromEntries(ADDONS.map((path, i) => [path, addons[i]])) as Record<AddonPath, string>,
        revision: `r${(lib as { REVISION?: string }).REVISION ?? ''}`,
      };
    })().catch((err) => {
      cached = null;
      throw err;
    });
  }
  return cached;
}
