/**
 * The pictures a person attached, put into the page a reply wrote.
 *
 * A page asks for a picture by name (`<img src="photo-1.jpg">`): the backend
 * gave each attached picture that name and told the model only the names
 * (`attachments/pictures.py`), because a 2 MB photograph is ~2.7 MB of base64
 * and a local model's window cannot hold it. The bytes are put in here, in the
 * window, at the last moment -- when the page is run, checked or saved -- and
 * **only in that copy**. The page the model is shown on a follow-up ("make the
 * header photo bigger") is still the one with names in it, so its SEARCH lines
 * match and nothing that big is ever sent back.
 *
 * Replaced everywhere a name can sit as a file reference: `src`, `srcset`,
 * `poster`, CSS `url()`, and a string in a script. As `data:` URIs, which the
 * preview's policy already allows (`img-src data:`) and which keep a saved page
 * one self-contained file. A multi-file app is saved as text files
 * (`POST /apps/save` takes `content: str`), so there the pictures are inlined
 * into the files rather than written next to them.
 *
 * Pure. The bytes arrive already fetched (`pictureStore`).
 */
import { pageOf } from '@/lib/pageEdits';
import type { PreviewableBlock } from '@/lib/previewableCode';
import { creditsHtml, swapPhotos, withCredits } from '@/lib/pagePhotos';

/** An attached picture as a user turn records it. */
export interface TurnPicture {
  id: string;
  kind: string;
  pageName?: string;
}

interface Turn {
  role: string;
  attachments?: readonly TurnPicture[];
}

/** What a name stands for: the picture as a `data:` URI, or `null` when its
 *  bytes are no longer to be had. A name with no entry is not one of ours. */
export type PictureMap = Record<string, string | null>;

const TEXT_FILE = /\.(?:html?|css|m?js|json|svg|txt|md)$/i;

/** Names are matched without regard to case, as the backend compares them. */
const keyOf = (name: string) => name.toLowerCase();

/** The pictures attached to the conversation up to and including `index`, by
 *  name. A later picture with the same name wins: the backend only repeats a
 *  name after an eviction, and the newer picture is the one the model saw. */
export function attachedPictures(turns: readonly Turn[], index: number): TurnPicture[] {
  const byName = new Map<string, TurnPicture>();
  for (let i = 0; i <= index && i < turns.length; i++) {
    if (turns[i].role !== 'user') continue;
    for (const a of turns[i].attachments ?? []) {
      if (a.kind === 'image' && a.pageName) byName.set(keyOf(a.pageName), a);
    }
  }
  return [...byName.values()];
}

/** The map for the reply at `index`. `held` is what has been fetched so far, by
 *  attachment id: a string is the picture, `null` is "gone", and an id not in
 *  it has not been fetched yet and is left out (the name is not replaced until
 *  its bytes arrive, rather than shown as gone). */
export function pictureMapFor(
  turns: readonly Turn[],
  index: number,
  held: Readonly<Record<string, string | null>>,
): PictureMap {
  const map: PictureMap = {};
  for (const a of attachedPictures(turns, index)) {
    const bytes = held[a.id];
    if (bytes !== undefined) map[keyOf(a.pageName!)] = bytes;
  }
  return map;
}

/** Ids of the attached pictures whose names a reply mentions -- the only ones
 *  worth fetching, so a conversation full of photographs costs nothing until a
 *  page uses one. */
export function idsNamedIn(turns: readonly Turn[], index: number, replyText: string): string[] {
  const text = replyText.toLowerCase();
  return attachedPictures(turns, index)
    .filter((a) => text.includes(keyOf(a.pageName!)))
    .map((a) => a.id);
}

/** Said in the page itself where a picture's bytes are no longer to be had, so
 *  the gap is visible on the page rather than a broken-image icon. ASCII, and
 *  base64 rather than percent-encoding, because it also lands inside an
 *  unquoted CSS `url()` where a parenthesis would end it. */
export function placeholderFor(name: string): string {
  const label = `${name} is no longer attached`;
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">' +
    '<rect width="600" height="400" fill="#e5e7eb"/>' +
    '<text x="300" y="205" font-family="sans-serif" font-size="22" text-anchor="middle" fill="#4b5563">' +
    label.replace(/[^A-Za-z0-9 ._-]/g, '') +
    '</text></svg>';
  return `data:image/svg+xml;base64,${btoa(svg)}`;
}

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** `name` as a file reference: optionally behind up to three folders (`images/`,
 *  `./`, `../img/`), never behind a scheme, a host or a longer word. */
function referenceTo(names: readonly string[]): RegExp {
  const alternation = [...names].sort((a, b) => b.length - a.length).map(escape).join('|');
  return new RegExp(
    `(?<![\\w:/.@%+-])(?:\\.{0,2}/)?(?:[\\w.-]{1,30}/){0,3}(${alternation})(?![\\w-])`,
    'gi',
  );
}

function swapNames(text: string, pictures: PictureMap): string {
  const names = Object.keys(pictures);
  if (!names.length) return text;
  return text.replace(referenceTo(names), (_all, name: string) => {
    const bytes = pictures[keyOf(name)];
    return bytes ?? placeholderFor(name);
  });
}

/** The block as it is to be run, checked or saved: names replaced by pictures.
 *  The block itself -- what is shown as code, copied, or sent back to the model
 *  -- is left with names. A block with no pictures comes back as it is. */
export function inlinePictures<T extends PreviewableBlock>(block: T): T {
  const pictures = block.pictures ?? {};
  // Photographs found online for the page's `photo:` descriptions go in at the
  // same moment, with their credits at the foot of the page. `pagePhotos.ts`.
  const photos = block.photoRefs ? (block.photos ?? {}) : null;
  if (!Object.keys(pictures).length && !photos) return block;
  const credits = photos ? creditsHtml(photos) : '';
  const swap = (code: string) => {
    const named = Object.keys(pictures).length ? swapNames(code, pictures) : code;
    return photos ? swapPhotos(named, photos) : named;
  };
  if (block.files) {
    // The credits go on the page a visitor opens: index.html, else the first page.
    const pages = block.files.filter((f) => /\.html?$/i.test(f.path));
    const entry = pages.find((f) => /(^|\/)index\.html?$/i.test(f.path)) ?? pages[0];
    const files = block.files.map((f) => {
      if (!TEXT_FILE.test(f.path)) return f;
      const code = swap(f.code);
      return { ...f, code: f === entry ? withCredits(code, credits) : code };
    });
    const page = pageOf(files);
    return {
      ...block,
      files,
      code: page ? page.code : block.code,
      ...(page ? { modules: page.modules } : {}),
    };
  }
  return { ...block, code: withCredits(swap(block.code), credits) };
}

const IMAGE_EXT = 'png|jpe?g|gif|webp|bmp|avif';
const ATTRIBUTE_REF = new RegExp(`\\b(?:src|poster|data-src)\\s*=\\s*["']?([^"'\\s>]+?\\.(?:${IMAGE_EXT}))(?=[\\s"'>?#])`, 'gi');
const SRCSET_REF = new RegExp(`\\bsrcset\\s*=\\s*"([^"]+)"`, 'gi');
const CSS_REF = new RegExp(`url\\(\\s*["']?([^"')\\s]+?\\.(?:${IMAGE_EXT}))(?=[\\s"')?#])`, 'gi');

/** File names an image reference in `text` points at, relative ones only. */
function relativeImages(text: string): string[] {
  const found: string[] = [];
  const take = (ref: string) => {
    if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(ref)) return;
    found.push(ref.split(/[?#]/)[0].replace(/\\/g, '/').split('/').pop()!.toLowerCase());
  };
  for (const m of text.matchAll(ATTRIBUTE_REF)) take(m[1]);
  for (const m of text.matchAll(CSS_REF)) take(m[1]);
  for (const m of text.matchAll(SRCSET_REF)) {
    for (const part of m[1].split(',')) {
      const url = part.trim().split(/\s+/)[0];
      if (new RegExp(`\\.(?:${IMAGE_EXT})(?:[?#]|$)`, 'i').test(url)) take(url);
    }
  }
  return found;
}

/**
 * What to tell the person about the pictures in this page, as plain sentences.
 *
 * Two things can be wrong and neither is allowed to be silent. A picture that
 * *was* attached but whose bytes are gone (the app restarted, or it was
 * removed, or pruned to keep the kept pictures under their ceiling) is shown as
 * a visible placeholder, and said here. And a reference to a picture the page
 * does not contain -- one attached to a conversation before conversations kept
 * their pictures, or a file name the model made up -- would otherwise be a
 * blank box with no explanation.
 */
export function pictureNotes(block: PreviewableBlock): string[] {
  const text = block.files ? block.files.map((f) => f.code).join('\n') : block.code;
  const pictures = block.pictures ?? {};
  const notes: string[] = [];

  const gone = Object.keys(pictures).filter(
    (name) => pictures[name] === null && new RegExp(`(?<![\\w-])${escape(name)}(?![\\w-])`, 'i').test(text),
  );
  if (gone.length) {
    notes.push(
      `${gone.join(', ')} ${gone.length === 1 ? 'is' : 'are'} no longer attached, so the page shows a grey placeholder where ` +
        `${gone.length === 1 ? 'it goes' : 'they go'}. Attach ${gone.length === 1 ? 'it' : 'them'} again and ask for the change.`,
    );
  }

  const own = new Set((block.files ?? []).map((f) => f.path.split('/').pop()!.toLowerCase()));
  const missing = [...new Set(relativeImages(text))].filter((name) => !(name in pictures) && !own.has(name));
  if (missing.length) {
    const shown = missing.slice(0, 3).join(', ') + (missing.length > 3 ? ` and ${missing.length - 3} more` : '');
    notes.push(
      `The page refers to ${shown}, which ${missing.length === 1 ? 'is' : 'are'} not part of it, so ` +
        `${missing.length === 1 ? 'it shows' : 'they show'} as a blank box. Zaram has no picture by ${missing.length === 1 ? 'that name' : 'those names'} ` +
        'in this conversation: attach it again to put it in.',
    );
  }
  return notes;
}
