/**
 * The key out of whatever was pasted.
 *
 * Provider pages put a **Copy** button on a code sample, next to the key,
 * and the sample is what people copy — the maintainer did, on 14 September
 * 2026, from build.nvidia.com: forty lines of Python with the key inside
 * `api_key = "…"`, pasted into a field that wanted twelve words of it. The
 * field said nothing, the connect stored the whole snippet as the key, and
 * "it doesn't work" was the report.
 *
 * So the field reads what it was given. A bare key is taken as is. Anything
 * that is plainly not one — several lines, quotes, an assignment, a URL
 * beside it — is searched for the one token that looks like a key, and the
 * person is told what was kept. Nothing is guessed silently: where no token
 * qualifies the paste is left alone, so a key of an unfamiliar shape is not
 * destroyed by being tidied.
 */

export interface PastedKey {
  /** What should go in the field. */
  key: string;
  /** True when the key was lifted out of something larger — code, a URL,
   *  a `Bearer` header — and the person should be told. */
  extracted: boolean;
}

/** Things a key never contains, whose presence says "this is not a key". */
const NOT_A_KEY = /[\s"'`=(){}[\];,<>]|https?:\/\//;

/** The shapes keys come in: a run of key characters, long enough to be one.
 *  Prefixed shapes are matched first so the key wins over a longer token
 *  beside it (a model name, an URL path). */
const KEY_SHAPES: RegExp[] = [
  /\b(?:nvapi|sk-or-v\d|sk-ant|sk-proj|sk|gsk|xai|csk|tgp_v\d|AIza)[-_][A-Za-z0-9_\-]{16,}/,
  /\b[A-Za-z0-9_\-]{24,}\b/,
];

/** Where the key sits in code, take that value ahead of any other token. */
const ASSIGNED = /(?:api[_-]?key|apiKey|token|secret|authorization|bearer)\s*[:=]?\s*["'`]?\s*(?:Bearer\s+)?([A-Za-z0-9_\-]{16,})/i;

export function pastedKey(raw: string): PastedKey {
  const text = raw.replace(/^﻿/, '');
  const trimmed = text.trim();
  if (!trimmed) return { key: '', extracted: false };
  if (!NOT_A_KEY.test(trimmed)) return { key: trimmed, extracted: false };

  const assigned = ASSIGNED.exec(text);
  if (assigned) return { key: assigned[1], extracted: true };

  for (const shape of KEY_SHAPES) {
    const match = shape.exec(text);
    if (match) {
      const token = match[0];
      // A URL fragment or a model name can be long too; refuse anything
      // that sits inside a URL or a path.
      const before = text.slice(Math.max(0, match.index - 1), match.index);
      if (before === '/' || before === '.') continue;
      return { key: token, extracted: true };
    }
  }
  // Nothing in it looks like a key. Hand back what was pasted, untouched,
  // so the person sees exactly what they gave and can fix it themselves.
  return { key: trimmed, extracted: false };
}
