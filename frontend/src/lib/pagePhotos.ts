/**
 * Real photographs in a page the model wrote, found after it was written.
 *
 * For a site that wants them -- a tourism site, a restaurant, a portfolio --
 * the model is told to describe each photograph rather than invent an address
 * (`backend/packs/photos/page.py`): `<img src="photo:Lagos beach at sunset">`.
 * The window reads those descriptions here, asks the backend for a credited,
 * openly licensed picture for each (`photoStore`, which goes through the
 * egress gate and asks the person once), and puts the pictures in at the last
 * moment, exactly as attached pictures are (`pagePictures.inlinePictures`): in
 * the copy that is run, checked or saved, never in the page the model is shown
 * again, so a follow-up's SEARCH lines still match.
 *
 * **Every picture carries its credit.** Most open licences require naming the
 * photographer, so a page with found photos gets a credits line at its foot,
 * built only from what the source returned. A photograph that could not be
 * found is a labelled placeholder saying why -- never a guessed picture.
 *
 * Pure. The pictures arrive already fetched.
 */
import type { PreviewableBlock } from '@/lib/previewableCode';

/** A photograph the backend found, ready to put in. */
export interface FoundPhoto {
  uri: string;
  title: string;
  creator: string;
  license: string;
  licenseUrl: string;
  sourceUrl: string;
  /** Where it was found ("Openverse", "Wikimedia Commons"), as the backend named
   *  it. Each photo is credited to its own source; empty when not given. */
  source?: string;
}

/** A description that came back without a picture, and the backend's reason. */
export interface MissingPhoto {
  error: string;
  code: string;
}

export type PhotoEntry = FoundPhoto | MissingPhoto;

/** Keyed by `photoKey`. A description with no entry has not been looked up. */
export type PhotoMap = Record<string, PhotoEntry>;

export const isFound = (entry: PhotoEntry | undefined): entry is FoundPhoto =>
  !!entry && 'uri' in entry;

/** The identity of a description, as the backend's `description_key` reads it:
 *  its letters and digits, lower-cased, one space apart. So `Lagos  Beach` and
 *  `lagos beach` are one photograph and one request. */
export function photoKey(description: string): string {
  return (description.normalize('NFKC').toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []).join(' ');
}

/** The template words of the guidance itself, which a small model sometimes
 *  copies; a reference made of them describes nothing. */
const TEMPLATE = photoKey('short description of the photo');

const ATTR = /(\b(?:src|srcset|data-src|poster|content)\s*=\s*(["']))\s*photo:(.*?)\2/gis;
const CSS = /(url\(\s*(["']?))\s*photo:(.*?)\2(\s*\))/gis;
/** `photo:beach 2x` -- a srcset density or width after the reference. */
const SRCSET_TAIL = /\s+\d+(?:\.\d+)?[wx]\s*$/i;

function decode(raw: string): string {
  let text = raw;
  try {
    text = decodeURIComponent(raw);
  } catch {
    // Not percent-encoded, or a stray `%`: read as written.
  }
  return text
    .replace(/&quot;/g, '"')
    .replace(/&#0?39;|&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .trim();
}

const split = (raw: string): [string, string] => {
  const tail = SRCSET_TAIL.exec(raw);
  return tail ? [raw.slice(0, tail.index), tail[0]] : [raw, ''];
};

/** Every distinct `photo:` description in `text`, in order of appearance.
 *
 *  Order matters because only the first eight are fetched, and the first photo
 *  on a page is usually its hero -- which is often a CSS background. Reading
 *  attributes first and stylesheets after put the hero last and past the limit,
 *  measured on a live tourism page. */
export function photoDescriptions(text: string): string[] {
  const hits = [...text.matchAll(ATTR), ...text.matchAll(CSS)].sort((a, b) => (a.index ?? 0) - (b.index ?? 0));
  const found = new Map<string, string>();
  for (const m of hits) {
    const description = decode(split(m[3])[0]);
    const key = photoKey(description);
    if (key && key !== TEMPLATE && !found.has(key)) found.set(key, description);
  }
  return [...found.values()];
}

/** Every description a block's page uses, across its files. */
export function blockPhotoDescriptions(block: PreviewableBlock): string[] {
  const text = block.files ? block.files.map((f) => f.code).join('\n') : block.code;
  return photoDescriptions(text);
}

/** The block with the photographs it uses attached, from what has been found
 *  so far. Recomputed from the page itself, so a block captured before the
 *  photographs arrived picks them up when it is next shown. */
export function withPhotos<T extends PreviewableBlock>(block: T, found: PhotoMap): T {
  const descriptions = blockPhotoDescriptions(block);
  if (!descriptions.length) return block;
  const photos: PhotoMap = {};
  for (const d of descriptions) {
    const entry = found[photoKey(d)];
    if (entry) photos[photoKey(d)] = entry;
  }
  return { ...block, photos, photoRefs: descriptions.length };
}

/** A grey card saying what should be here and why it is not. ASCII and base64
 *  for the reason `placeholderFor` gives: it lands inside CSS `url()` too. */
function photoPlaceholder(description: string, why: string): string {
  const clean = (s: string) => s.replace(/[^A-Za-z0-9 ,.:'-]/g, '').slice(0, 60);
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500">' +
    '<rect width="800" height="500" fill="#e5e7eb"/>' +
    '<text x="400" y="240" font-family="sans-serif" font-size="26" text-anchor="middle" fill="#374151">' +
    clean(description) +
    '</text>' +
    '<text x="400" y="280" font-family="sans-serif" font-size="18" text-anchor="middle" fill="#6b7280">' +
    clean(why) +
    '</text></svg>';
  return `data:image/svg+xml;base64,${btoa(svg)}`;
}

function pictureFor(description: string, photos: PhotoMap): string {
  const entry = photos[photoKey(description)];
  if (isFound(entry)) return entry.uri;
  if (entry) return photoPlaceholder(description, 'No photo: ' + entry.error);
  return photoPlaceholder(description, 'Finding a photo...');
}

/** `text` with every `photo:` reference replaced by its picture or placeholder. */
export function swapPhotos(text: string, photos: PhotoMap): string {
  return text
    .replace(ATTR, (_all, head: string, quote: string, raw: string) => {
      const [description, tail] = split(raw);
      return `${head}${pictureFor(decode(description), photos)}${tail}${quote}`;
    })
    .replace(CSS, (_all, head: string, quote: string, raw: string, close: string) => {
      return `${head}${pictureFor(decode(raw), photos)}${quote}${close}`;
    });
}

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

const safeLink = (url: string) => (/^https:\/\//i.test(url) ? url : '');

/** The credits line for the photographs a page shows, or `''` for none. Only
 *  what the source said: a picture with no named creator is not given one. */
export function creditsHtml(photos: PhotoMap): string {
  const items = Object.values(photos)
    .filter(isFound)
    .map((p) => {
      const title = esc(p.title || 'Photo');
      const named = safeLink(p.sourceUrl)
        ? `<a href="${esc(p.sourceUrl)}" target="_blank" rel="noopener">&ldquo;${title}&rdquo;</a>` // check-no-dead-links: allow -- a link in the page being built, opened in a browser once saved
        : `&ldquo;${title}&rdquo;`;
      const by = p.creator ? ` by ${esc(p.creator)}` : '';
      const licence = p.license
        ? safeLink(p.licenseUrl)
          ? `, <a href="${esc(p.licenseUrl)}" target="_blank" rel="noopener">${esc(p.license)}</a>` // check-no-dead-links: allow -- a link in the page being built, opened in a browser once saved
          : `, ${esc(p.license)}`
        : '';
      // Each photo says where it came from: a page can mix sources, and a line
      // that named only one would credit the other's photographs to it.
      const via = p.source ? ` (via ${esc(p.source)})` : '';
      return `${named}${by}${licence}${via}`;
    });
  if (!items.length) return '';
  return (
    '<footer data-zaram-photo-credits style="font:12px/1.6 system-ui,sans-serif;color:#4b5563;' +
    'background:#f3f4f6;padding:12px 16px;text-align:center">Photos: ' +
    items.join(' &middot; ') +
    '</footer>'
  );
}

/** `page` with the credits line placed at the foot of its body. */
export function withCredits(page: string, credits: string): string {
  if (!credits || page.includes('data-zaram-photo-credits')) return page;
  const close = page.search(/<\/body>/i);
  return close === -1 ? page + credits : page.slice(0, close) + credits + page.slice(close);
}

/**
 * Plain sentences about the photographs, for the line under the reply and the
 * preview's status line. A photograph that is still being looked for says
 * nothing: that is a wait, not a fault.
 */
export function photoNotes(block: PreviewableBlock): string[] {
  const photos = block.photos ?? {};
  const missing = Object.values(photos).filter((e): e is MissingPhoto => !isFound(e));
  if (!missing.length) return [];
  const declined = missing.filter((m) => m.code === 'consent_declined' || m.code === 'consent_unanswered');
  if (declined.length === missing.length) {
    return [
      'Zaram did not search for photos, so the page shows labelled placeholders. ' +
        'Press Find photos again to be asked once more.',
    ];
  }
  const n = missing.length;
  const reasons = [...new Set(missing.map((m) => m.error))].slice(0, 2).join(' ');
  return [`${n} ${n === 1 ? 'photo was' : 'photos were'} not found and ${n === 1 ? 'shows' : 'show'} as a labelled placeholder. ${reasons}`];
}

/** Reasons that looking again could change: a refusal, no answer, the
 *  connection, the rate limit, or the time budget running out (`busy`) -- not
 *  "nothing matched". */
export const RETRIABLE_CODES: readonly string[] = [
  'consent_declined',
  'consent_unanswered',
  'offline',
  'rate_limited',
  'busy',
];

/** Whether looking again could change anything. */
export function canLookAgain(block: PreviewableBlock): boolean {
  return Object.values(block.photos ?? {}).some((e) => !isFound(e) && RETRIABLE_CODES.includes(e.code));
}
