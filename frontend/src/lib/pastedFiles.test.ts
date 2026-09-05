/**
 * Pasting a screenshot into the message box.
 *
 * Queue item 3. The paperclip and a drag both reached `takeFiles`; Ctrl+V did
 * nothing, so the gesture a person uses immediately after taking a screenshot
 * was the one that was not wired.
 *
 * These test the clipboard reading and the naming rather than the component,
 * because those are the two places this can be wrong in a way nobody notices:
 * a browser that populates `items` but not `files` loses every paste on one
 * platform and none on another, and a placeholder name makes two chips
 * identical. The wiring itself — `onPaste` on the input — is a compile-checked
 * prop, which is the same reasoning `NoticeCard.test.tsx` records for its own
 * required-prop guard.
 */
import { describe, expect, it } from 'vitest';

import { filesFromClipboard, withPasteName } from './pastedFiles';

/** A `DataTransfer` shaped like the ones browsers actually hand over.
 *
 *  Built by hand because jsdom's `DataTransfer` carries neither a usable
 *  `items` list nor `files`, so a test using the real one would assert against
 *  an empty object and pass whatever the code did. */
function clipboard(options: { items?: Array<{ kind: string; file: File | null }>; files?: File[] }) {
  return {
    items: (options.items ?? []).map((entry) => ({
      kind: entry.kind,
      getAsFile: () => entry.file,
    })),
    files: options.files ?? [],
  } as unknown as DataTransfer;
}

function png(name: string, type = 'image/png') {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type });
}

describe('reading files off the clipboard', () => {
  it('finds a screenshot that arrived as an item', () => {
    const shot = png('image.png');
    expect(filesFromClipboard(clipboard({ items: [{ kind: 'file', file: shot }] }))).toEqual([shot]);
  });

  it('finds a file that arrived only in `files`', () => {
    /* Copying a file from a folder populates `files`, and on some platforms
       leaves `items` empty. Reading one source only loses one of the two ways
       a person puts a picture on the clipboard. */
    const doc = png('contract-v3.png');
    expect(filesFromClipboard(clipboard({ files: [doc] }))).toEqual([doc]);
  });

  it('ignores the text that rides alongside a copied file', () => {
    /* A paste carries several representations at once — an image item and a
       `text/plain` item naming it. Only the file is an attachment. */
    const shot = png('image.png');
    const found = filesFromClipboard(
      clipboard({ items: [{ kind: 'string', file: null }, { kind: 'file', file: shot }] }),
    );
    expect(found).toEqual([shot]);
  });

  it('returns nothing for an ordinary text paste', () => {
    /* The load-bearing case. An empty result is what tells the handler to
       leave the event alone, and a paste that stopped typing from working
       would be a far worse bug than the one being fixed. */
    expect(filesFromClipboard(clipboard({ items: [{ kind: 'string', file: null }] }))).toEqual([]);
    expect(filesFromClipboard(null)).toEqual([]);
  });

  it('survives an item that claims to be a file and yields none', () => {
    expect(filesFromClipboard(clipboard({ items: [{ kind: 'file', file: null }] }))).toEqual([]);
  });
});

describe('naming what was pasted', () => {
  const at = new Date(2026, 7, 28, 14, 32, 11);

  it('gives a clipboard screenshot the time it was pasted', () => {
    /* Chromium names every clipboard image `image.png`, so two pastes produce
       two chips the user cannot tell apart — including when deciding which one
       to remove. */
    expect(withPasteName(png('image.png'), at).name).toBe('pasted-2026-08-28-143211.png');
  });

  it('keeps the real name of a file copied from a folder', () => {
    /* The name is what the user recognises in a chip. Renaming it would be the
       feature removing information rather than adding it. */
    const doc = png('contract-v3.png');
    expect(withPasteName(doc, at)).toBe(doc);
  });

  it('normalises the extension rather than trusting the browser', () => {
    /* The same photograph is `image/jpeg` everywhere and arrives named `.jpg`
       in one browser and `.jpeg` in another. A suffix a parser dispatches on
       must not depend on which one did the encoding. */
    expect(withPasteName(png('image.jpeg', 'image/jpeg'), at).name).toBe(
      'pasted-2026-08-28-143211.jpg',
    );
  });

  it('leaves a file alone when no extension can be established', () => {
    /* A name with no suffix reaches a parser that dispatches on suffix, and a
       guess there fails in a way that reads as the file being unsupported.
       Doing nothing is the honest option. */
    const nameless = new File([new Uint8Array([1])], '', { type: 'application/octet-stream' });
    expect(withPasteName(nameless, at)).toBe(nameless);
  });

  it('carries the type and the bytes across the rename', () => {
    /* `new File([file], ...)` is a copy, and a copy that dropped the MIME type
       would reach the backend as an unknown kind — the vision gate reads it. */
    const renamed = withPasteName(png('image.png'), at);
    expect(renamed.type).toBe('image/png');
    expect(renamed.size).toBe(4);
  });
});
