/**
 * Files on the clipboard, as the composer needs them.
 *
 * Two jobs, both small, both here rather than inside `ChatSurface` so they can
 * be tested without rendering a component that pulls in four stores, a speech
 * engine and an orb.
 *
 * There is a paste handler in `KnowledgeWorkspace` already and this is
 * deliberately not it. That one listens on `window` and **skips** fields,
 * because a paste into the search box there is a search and not an ingest.
 * The chat case is the opposite: the caret is in the message box, that is
 * where a screenshot is pasted, and a handler that skipped fields would never
 * fire. Same word, opposite rule, so sharing the code would have meant a flag
 * deciding which product it was — which is how one function comes to serve two
 * behaviours and get both slightly wrong.
 */

/** Files a paste carried, or an empty array for an ordinary text paste.
 *
 *  Reads `items` first and `files` second. A screenshot taken by the operating
 *  system arrives as a `DataTransferItem` of kind `file`, and
 *  `DataTransfer.files` is not reliably populated for it — while a file
 *  *copied from a folder* populates `files` and may not appear in `items` at
 *  all. Reading only one of them loses one of the two ways a person puts a
 *  picture on the clipboard, and which one is lost varies by platform, which
 *  is the worst kind of bug to be told about second-hand.
 *
 *  Returning `[]` is the signal to leave the event alone. Text pasted into the
 *  message box must behave exactly as it always has; a handler that swallowed
 *  a paste it had no files for would break typing to serve attaching.
 */
export function filesFromClipboard(data: DataTransfer | null): File[] {
  if (!data) return [];

  const fromItems = Array.from(data.items ?? [])
    .filter((item) => item.kind === 'file')
    .map((item) => item.getAsFile())
    .filter((file): file is File => file != null);

  if (fromItems.length > 0) return fromItems;
  return Array.from(data.files ?? []);
}

/** Extensions for the image types a clipboard actually carries.
 *
 *  A map rather than `type.split('/')[1]`, because that yields `.jpeg` for one
 *  browser and `.jpg` for another on the same picture, and `.svg+xml` for a
 *  copied vector. A name is shown to the user and a suffix is read by the
 *  parser; neither should depend on which browser did the encoding.
 */
const EXTENSION_FOR_TYPE: Record<string, string> = {
  'image/png': '.png',
  'image/jpeg': '.jpg',
  'image/gif': '.gif',
  'image/webp': '.webp',
  'image/bmp': '.bmp',
  'image/svg+xml': '.svg',
};

/** The names a browser invents when the clipboard image never had one. */
const PLACEHOLDER_NAMES = new Set(['', 'image.png', 'image.jpeg', 'image.jpg', 'image.webp']);

function stamp(now: Date): string {
  const two = (n: number) => String(n).padStart(2, '0');
  return (
    `${now.getFullYear()}-${two(now.getMonth() + 1)}-${two(now.getDate())}` +
    `-${two(now.getHours())}${two(now.getMinutes())}${two(now.getSeconds())}`
  );
}

/**
 * Give a pasted screenshot a name that tells it apart from the next one.
 *
 * Chromium hands every clipboard image the name `image.png`, so pasting two
 * screenshots produces two chips reading `image.png` and the user cannot tell
 * which is the one they meant to remove. The time it was pasted is the only
 * thing that distinguishes them, and it is a fact rather than a guess.
 *
 * **Only the placeholder names are replaced.** A file copied from a folder
 * arrives with its real name — `contract-v3.pdf` — and that is what the user
 * recognises in a chip; renaming it would be the feature actively removing
 * information. Anything not on the placeholder list is returned untouched,
 * including the `File` object itself, so nothing is copied that need not be.
 *
 * A file whose extension cannot be established is also left alone. A name with
 * no suffix reaches a parser that dispatches on suffix, and a wrong guess
 * there fails in a way that reads as the file being unsupported.
 */
export function withPasteName(file: File, now: Date = new Date()): File {
  if (!PLACEHOLDER_NAMES.has(file.name.toLowerCase())) return file;

  const fromName = file.name.includes('.') ? file.name.slice(file.name.lastIndexOf('.')) : '';
  const extension = EXTENSION_FOR_TYPE[file.type.toLowerCase()] ?? fromName;
  if (!extension) return file;

  return new File([file], `pasted-${stamp(now)}${extension}`, {
    type: file.type,
    lastModified: file.lastModified,
  });
}
