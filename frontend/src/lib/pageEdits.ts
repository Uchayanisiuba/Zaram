/**
 * A change to a page, written as the lines that change rather than the page again.
 *
 * Asked for 11 October 2026, after a Minecraft-style game took an afternoon and
 * never played. Every fix, from the check or from the person, asked for "the whole
 * page in one block": 60,000 characters written again at ~20 characters a second,
 * twenty minutes or more each, and every rewrite a fresh chance to break something
 * that worked. A harness running the same model edits the lines that are wrong and
 * leaves the rest alone. This is that, for a page in the chat.
 *
 * **The format is the one coding models are trained on** (aider's SEARCH/REPLACE):
 *
 *     game.js
 *     <<<<<<< SEARCH
 *     lines copied exactly from the current file
 *     =======
 *     the lines that replace them
 *     >>>>>>> REPLACE
 *
 * The file is named on the line above the block or on its fence line; a page of
 * one file needs no name. An empty SEARCH with a name nobody has yet is a new file.
 *
 * **A change that does not match is reported, never guessed.** Exact text first,
 * then the same lines with trailing spaces and line endings ignored; anything
 * looser could land a change in the wrong place, which is worse than asking again.
 * The failures travel with the result so the check can say which block missed.
 */
import { bundleApp, normalisePath, type AppFile } from '@/lib/appFiles';

export interface PageEdit {
  /** The file the block names, or `null` for a page of one file. */
  file: string | null;
  search: string;
  replace: string;
}

export interface EditResult {
  files: AppFile[];
  applied: number;
  /** Blocks that matched nothing, with why, in the order they were written. */
  failed: { edit: PageEdit; reason: string }[];
}

const BLOCK = /<{5,9} ?SEARCH[^\n]*\r?\n([\s\S]*?)\r?\n?={5,9}[ \t]*\r?\n([\s\S]*?)\r?\n?>{5,9} ?REPLACE/g;
const FILE_NAME = /([\w][\w./-]*\.(?:html?|css|m?js|json|svg|txt|md))\b/i;

/** The SEARCH/REPLACE blocks in a reply, or `[]`. */
export function extractEdits(text: string): PageEdit[] {
  if (!text || !/<{5,9} ?SEARCH/.test(text)) return [];
  const edits: PageEdit[] = [];
  let match: RegExpExecArray | null;
  BLOCK.lastIndex = 0;
  while ((match = BLOCK.exec(text)) !== null) {
    edits.push({ file: nameAbove(text.slice(0, match.index)), search: match[1], replace: match[2] });
  }
  return edits;
}

/** The file named just above a block: on the line before it, or on the fence
 *  that opened it. Two lines back at most, so a name mentioned in prose further
 *  up is not taken for the target. */
function nameAbove(before: string): string | null {
  const lines = before.split(/\r?\n/);
  if (lines.length && lines[lines.length - 1].trim() === '') lines.pop();
  for (let i = lines.length - 1, seen = 0; i >= 0 && seen < 2; i--, seen++) {
    const line = lines[i].trim();
    if (!line) continue;
    const hit = FILE_NAME.exec(line.replace(/^```\s*[\w+-]*\s*/, ''));
    if (hit) return normalisePath(hit[1]);
    if (!line.startsWith('```')) return null;
  }
  return null;
}

const tidy = (text: string) => text.replace(/\r\n?/g, '\n').replace(/[ \t]+$/gm, '');

/** Where `search` sits in `code`: exact, then ignoring trailing spaces and line
 *  endings. `null` when it is in neither form. */
function locate(code: string, search: string): { start: number; end: number; code: string } | null {
  const exact = code.indexOf(search);
  if (exact >= 0) return { start: exact, end: exact + search.length, code };
  const loose = tidy(code);
  const needle = tidy(search);
  const at = needle ? loose.indexOf(needle) : -1;
  return at >= 0 ? { start: at, end: at + needle.length, code: loose } : null;
}

function targetFor(files: AppFile[], name: string | null): AppFile | null {
  if (!name) {
    if (files.length === 1) return files[0];
    return files.find((f) => /(^|\/)index\.html?$/i.test(f.path)) ?? null;
  }
  const lower = name.toLowerCase();
  const exact = files.find((f) => f.path.toLowerCase() === lower);
  if (exact) return exact;
  const base = lower.split('/').pop()!;
  const same = files.filter((f) => f.path.toLowerCase().split('/').pop() === base);
  if (same.length === 1) return same[0];
  // A page of one file, named by whatever the model chose to call it.
  return files.length === 1 && /\.html?$/i.test(name) ? files[0] : null;
}

/** `files` with every edit applied in order. Never throws; a miss is a failure
 *  in the result, and the rest still apply. */
export function applyEdits(files: readonly AppFile[], edits: readonly PageEdit[]): EditResult {
  const out = files.map((f) => ({ ...f }));
  const failed: EditResult['failed'] = [];
  let applied = 0;
  for (const edit of edits) {
    const target = targetFor(out, edit.file);
    if (!target) {
      if (edit.file && !edit.search.trim()) {
        out.push({ path: edit.file, code: edit.replace });
        applied++;
      } else {
        failed.push({ edit, reason: `there is no file called ${edit.file ?? '(unnamed)'} in the page` });
      }
      continue;
    }
    if (!edit.search.trim()) {
      failed.push({ edit, reason: `the change to ${target.path} has nothing in its SEARCH part` });
      continue;
    }
    const where = locate(target.code, edit.search);
    if (!where) {
      failed.push({ edit, reason: `the SEARCH lines for ${target.path} are not in the file as it stands` });
      continue;
    }
    target.code = where.code.slice(0, where.start) + edit.replace + where.code.slice(where.end);
    applied++;
  }
  return { files: out, applied, failed };
}

/** A page of one file as the files the edits are applied to. */
export function asFiles(code: string): AppFile[] {
  return [{ path: 'index.html', code }];
}

/** The joined page for a set of files: the one file itself, or the bundle. */
export function pageOf(files: readonly AppFile[]): { code: string; modules: boolean } | null {
  if (files.length === 1) return { code: files[0].code, modules: false };
  const bundled = bundleApp(files);
  return bundled ? { code: bundled.html, modules: bundled.modules } : null;
}

/**
 * Loops whose step is the bare counter -- `for (let z = a; z <= b; z)` -- with
 * the missing `++` (or `--`) put back.
 *
 * Measured 11 October 2026 on the resident Qwen3.8-27B at 2.2 bits: one loop in
 * twenty-six came out without its increment, the same defect a draft on 5 October
 * had twenty-three times. The page freezes on the first frame, the check catches
 * it, and the fix used to cost a whole rewrite. There is exactly one reading of
 * such a loop -- a step that is only the counter's name does nothing, and the
 * condition says which way it counts -- so it is repaired rather than reported,
 * and the repair is listed so the person is told it happened.
 */
export function repairLoops(code: string): { code: string; repaired: string[] } {
  const repaired: string[] = [];
  const fixed = code.replace(
    /for\s*\(\s*((?:let|var|const)?\s*([A-Za-z_$][\w$]*)\s*=[^;]*;\s*\2\s*(<=?|>=?)[^;]*;\s*)\2(\s*\))/g,
    (all: string, head: string, name: string, op: string, close: string, at: number, source: string) => {
      // A body that steps the counter itself (`i += 2`) is not missing a step;
      // adding one would skip half of it. Left for the check to report.
      if (assignsIn(bodyAfter(source, at + all.length), name)) return all;
      const step = op.startsWith('<') ? `${name}++` : `${name}--`;
      repaired.push(`for (${head}${name}) → ${step}`);
      return `for (${head}${step}${close}`;
    },
  );
  return { code: fixed, repaired };
}

/** The statement a loop header governs: a `{…}` block, or one statement --
 *  which may itself be a loop with a block (`for (…) for (…) { … }`). */
function bodyAfter(source: string, from: number): string {
  let depth = 0;
  for (let i = from; i < source.length; i++) {
    const ch = source[i];
    if (ch === '{' || ch === '(' || ch === '[') depth++;
    else if (ch === '}' || ch === ')' || ch === ']') {
      depth--;
      if (depth === 0 && ch === '}') return source.slice(from, i + 1);
      if (depth < 0) return source.slice(from, i);
    } else if (ch === ';' && depth === 0) return source.slice(from, i + 1);
  }
  return source.slice(from);
}

function assignsIn(body: string, name: string): boolean {
  const n = name.replace(/\$/g, '\\$');
  return new RegExp(`(?:\\+\\+|--)\\s*${n}\\b|\\b${n}\\s*(?:\\+\\+|--|[-+*/%]?=(?!=))`).test(body);
}

/** The page written out as a reply would carry it -- for sending back to the
 *  model, which must see the page as it now stands, not the edits that made it. */
export function asReply(files: readonly AppFile[]): string {
  if (files.length === 1) return '```html\n' + files[0].code + '\n```';
  return files
    .map((f) => {
      const lang = /\.css$/i.test(f.path) ? 'css' : /\.m?js$/i.test(f.path) ? 'js' : /\.html?$/i.test(f.path) ? 'html' : '';
      return '```' + lang + ' ' + f.path + '\n' + f.code + '\n```';
    })
    .join('\n\n');
}
