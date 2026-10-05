/**
 * An app written as several files in one reply, run without a project.
 *
 * Asked for 5 October 2026: *"I want Zaram to be able to do single file apps
 * and multiple file apps"*, not tied to a project. A project is where Zaram
 * runs commands, and a browser app of an `index.html`, a `style.css` and a
 * `game.js` runs no command: the browser reads the files. So the files are
 * joined here, in memory, into the one document the preview frame already
 * knows how to seal and run, and **nothing executes outside that frame**.
 *
 * **How a reply says which file is which.** Models label a fence three
 * different ways and all three are read: on the fence line (```html
 * index.html), as the first line of the block (`// game.js`), or as the line
 * just above it (**game.js**). Reading one convention would work for the
 * model it was tried on and silently fail for the next, which is the rule
 * against building for one model. A block with no name is not part of the app.
 *
 * **How the files are joined.** `<link rel="stylesheet">` becomes a `<style>`;
 * a classic `<script src>` becomes an inline script (a `defer` one moves to
 * the end of the body, because it was going to run after the document); a
 * module script, and every module it imports, goes through **one import map**
 * of `data:` URLs, with relative specifiers rewritten to bare names
 * (`./world.js` -> `zaram-app/world.js`). Bare names, because a module loaded
 * from a `data:` URL has no base to resolve `./` against. Because the
 * specifiers are fixed names rather than the other module's URL, two modules
 * that import each other do not need each other's text to build their own.
 *
 * What cannot be joined is anything fetched by path at run time -- a `.json`,
 * an image. The seal refuses `fetch` outright, so these are inlined by the page
 * or not used, and the guidance sent with a page request says so.
 */

export interface AppFile {
  /** Forward-slash path as the reply named it, without a leading `./`. */
  path: string;
  code: string;
}

export interface BundledApp {
  /** The entry page with everything joined into it. */
  html: string;
  /** Whether modules were written into `data:` URLs, which the page's
   *  policy has to allow. */
  modules: boolean;
  /** The path of the entry page. */
  entry: string;
}

const EXT = '(?:html?|css|m?js|json|svg|txt|md)';
const NAME_IN_FENCE = new RegExp(`([\\w][\\w./-]*\\.${EXT})\\b`, 'i');
const NAME_FIRST_LINE = new RegExp(
  `^[ \\t]*(?:\\/\\/|\\/\\*+|<!--|#)[ \\t]*(?:file(?:name)?[ \\t]*[:=-]?[ \\t]*)?([\\w][\\w./-]*\\.${EXT})[ \\t]*(?:\\*+\\/|-->)?[ \\t]*\\r?\\n`,
  'i',
);
const NAME_ABOVE = new RegExp(
  `^[\\s#*>\`_-]*(?:file(?:name)?\\s*[:=]?\\s*)?[\`*_]*([\\w][\\w./-]*\\.${EXT})[\`*_:]*\\s*$`,
  'i',
);

/** `a/./b/../c.js` -> `a/c.js`. Never climbs above the root. */
export function normalisePath(path: string): string {
  const out: string[] = [];
  for (const part of path.replace(/\\/g, '/').split('/')) {
    if (part === '' || part === '.') continue;
    if (part === '..') out.pop();
    else out.push(part);
  }
  return out.join('/');
}

function dirOf(path: string): string {
  return path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '';
}

function lastLine(text: string): string {
  const lines = text.split('\n');
  for (let i = lines.length - 1; i >= 0; i--) if (lines[i].trim()) return lines[i];
  return '';
}

/**
 * The named files in a reply, or `null` unless it is an app: at least two named
 * files, one of them a page. Tolerant of a fence still being written, because
 * this runs on streaming text. A name used twice keeps the later block -- a
 * model that rewrites a file in the same reply means the rewrite.
 */
export function extractAppFiles(text: string): AppFile[] | null {
  if (!text || !text.includes('```')) return null;
  const fence = /```[ \t]*([A-Za-z][\w+-]*)?([^\n]*)\n([\s\S]*?)(?:```|$)/g;
  const found = new Map<string, AppFile>();
  let match: RegExpExecArray | null;
  while ((match = fence.exec(text)) !== null) {
    let code = match[3].replace(/\r?\n$/, '');
    if (!code.trim()) continue;
    let name = NAME_IN_FENCE.exec(match[2])?.[1];
    if (!name) {
      const first = NAME_FIRST_LINE.exec(code);
      if (first) {
        name = first[1];
        code = code.slice(first[0].length);
      }
    }
    if (!name) name = NAME_ABOVE.exec(lastLine(text.slice(0, match.index)))?.[1];
    if (!name) continue;
    const path = normalisePath(name);
    if (!path) continue;
    found.set(path.toLowerCase(), { path, code });
  }
  const files = [...found.values()];
  if (files.length < 2 || !files.some((f) => /\.html?$/i.test(f.path))) return null;
  return files;
}

function inlineScript(text: string): string {
  return text.replace(/<\/script/gi, '<\\/script');
}

function inlineStyle(text: string): string {
  return text.replace(/<\/style/gi, '<\\/style');
}

function dataModule(text: string): string {
  return `data:text/javascript;charset=utf-8,${encodeURIComponent(text)}`;
}

function attr(tag: string, name: string): string | null {
  const m = new RegExp(`\\b${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`, 'i').exec(tag);
  return m ? (m[1] ?? m[2] ?? m[3] ?? null) : null;
}

const MODULE_SYNTAX = /^\s*(?:import\s*(?:[\w{*'"]|\()|export\s)/m;

/** Join the files of an app into the one page the preview frame runs, or
 *  `null` when there is no page to start from. Never throws. */
export function bundleApp(files: readonly AppFile[]): BundledApp | null {
  try {
    const entry =
      files.find((f) => /(^|\/)index\.html?$/i.test(f.path)) ?? files.find((f) => /\.html?$/i.test(f.path));
    if (!entry) return null;

    const byPath = new Map(files.map((f) => [f.path.toLowerCase(), f]));
    const resolve = (ref: string, fromDir: string): AppFile | null => {
      if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(ref)) return null;
      const clean = ref.split(/[?#]/)[0];
      const joined = normalisePath(clean.startsWith('/') ? clean : `${fromDir}/${clean}`);
      const exact = byPath.get(joined.toLowerCase());
      if (exact) return exact;
      // A model that labels `js/game.js` and writes `src="game.js"` is
      // consistent with itself and not with us. A unique file name is enough.
      const base = joined.split('/').pop()!.toLowerCase();
      const same = files.filter((f) => f.path.split('/').pop()!.toLowerCase() === base);
      return same.length === 1 ? same[0] : null;
    };

    const modules = new Map<string, string>();
    const key = (file: AppFile) => `zaram-app/${file.path}`;
    const addModule = (file: AppFile): void => {
      const name = key(file);
      if (modules.has(name)) return;
      modules.set(name, ''); // claimed first, so a cycle terminates
      const rewritten = file.code.replace(
        /(\bfrom\s*|\bimport\s*\(?\s*)(['"])([^'"\n]+)\2/g,
        (all, lead: string, quote: string, spec: string) => {
          if (!/^(?:\.{1,2}\/|\/)/.test(spec)) return all;
          const target = resolve(spec, dirOf(file.path));
          if (!target) return all;
          addModule(target);
          return `${lead}${quote}${key(target)}${quote}`;
        },
      );
      modules.set(name, rewritten);
    };

    const home = dirOf(entry.path);
    const deferred: string[] = [];
    let html = entry.code;

    html = html.replace(/<link\b[^>]*>/gi, (tag) => {
      if (!/rel\s*=\s*["']?stylesheet/i.test(tag)) return tag;
      const href = attr(tag, 'href');
      const file = href ? resolve(href, home) : null;
      return file ? `<style>\n${inlineStyle(file.code)}\n</style>` : tag;
    });

    html = html.replace(
      /<script\b([^>]*?)\bsrc\s*=\s*(?:"([^"]+)"|'([^']+)')([^>]*)>\s*<\/script>/gi,
      (tag, before: string, dq: string | undefined, sq: string | undefined, after: string) => {
        const file = resolve(dq ?? sq ?? '', home);
        if (!file) return tag;
        const attrs = `${before} ${after}`;
        if (/type\s*=\s*["']?module/i.test(attrs) || MODULE_SYNTAX.test(file.code)) {
          addModule(file);
          return `<script type="module">import "${key(file)}";</script>`;
        }
        const script = `<script>\n${inlineScript(file.code)}\n</script>`;
        if (/\b(?:defer|async)\b/i.test(attrs)) {
          deferred.push(script);
          return '';
        }
        return script;
      },
    );

    if (deferred.length) {
      const tail = deferred.join('\n');
      html = /<\/body>/i.test(html) ? html.replace(/<\/body>/i, () => `${tail}\n</body>`) : `${html}\n${tail}`;
    }

    // Modules written inline in the page import siblings too.
    html.replace(/<script\b[^>]*type\s*=\s*["']?module[^>]*>([\s\S]*?)<\/script>/gi, (all, body: string) => {
      body.replace(/(?:\bfrom\s*|\bimport\s*\(?\s*)(['"])(\.{0,2}\/?[^'"\n]+)\1/g, (_m, _q, spec: string) => {
        if (!/^(?:\.{1,2}\/|\/)/.test(spec)) return _m;
        const target = resolve(spec, home);
        if (target) addModule(target);
        return _m;
      });
      return all;
    });
    html = html.replace(
      /(<script\b[^>]*type\s*=\s*["']?module[^>]*>)([\s\S]*?)(<\/script>)/gi,
      (all, open: string, body: string, close: string) =>
        /\bsrc\s*=/.test(open)
          ? all
          : `${open}${body.replace(
              /(\bfrom\s*|\bimport\s*\(?\s*)(['"])([^'"\n]+)\2/g,
              (m, lead: string, quote: string, spec: string) => {
                if (!/^(?:\.{1,2}\/|\/)/.test(spec)) return m;
                const target = resolve(spec, home);
                return target ? `${lead}${quote}${key(target)}${quote}` : m;
              },
            )}${close}`,
    );

    if (modules.size) {
      const imports = Object.fromEntries([...modules].map(([name, code]) => [name, dataModule(code)]));
      let placed = false;
      html = html.replace(
        /(<script\b[^>]*type\s*=\s*["']importmap["'][^>]*>)([\s\S]*?)(<\/script>)/i,
        (all, open: string, json: string, close: string) => {
          try {
            const theirs = JSON.parse(json) as { imports?: Record<string, string> };
            placed = true;
            return `${open}${JSON.stringify({ ...theirs, imports: { ...(theirs.imports ?? {}), ...imports } })}${close}`;
          } catch {
            return all;
          }
        },
      );
      if (!placed) {
        const map = `<script type="importmap">${JSON.stringify({ imports })}</script>`;
        const anchor = /<head\b[^>]*>/i.exec(html) ?? /<html\b[^>]*>/i.exec(html) ?? /<!doctype[^>]*>/i.exec(html);
        html = anchor
          ? html.slice(0, anchor.index + anchor[0].length) + map + html.slice(anchor.index + anchor[0].length)
          : map + html;
      }
    }

    return { html, modules: modules.size > 0, entry: entry.path };
  } catch {
    return null;
  }
}

/** The first never-ending loop in any file, with the file named. */
export function stuckLoopIn(
  files: readonly AppFile[],
  find: (source: string) => { line: number; text: string } | null,
): { file: string; line: number; text: string } | null {
  for (const file of files) {
    if (!/\.(?:m?js|html?)$/i.test(file.path)) continue;
    const hit = find(file.code);
    if (hit) return { file: file.path, ...hit };
  }
  return null;
}
