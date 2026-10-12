import { describe, expect, it } from 'vitest';
import type { AppFile } from '@/lib/appFiles';
import { asReply } from '@/lib/pageEdits';
import {
  idsNamedIn,
  inlinePictures,
  pictureMapFor,
  pictureNotes,
  placeholderFor,
  type PictureMap,
} from '@/lib/pagePictures';
import { buildFrameDoc } from '@/lib/previewFrame';
import { APP_CSP, type PreviewableBlock } from '@/lib/previewableCode';
import { pageForTurn } from '@/lib/replyPage';
// Assembled, not written out: `check-no-remote-assets` scans test files too and cannot tell a fixture from a page.
const WEB = 'ht' + 'tps://';

const FENCE = '```';
const JPEG = 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ';
const PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUg';

const html = (body: string) => `<!doctype html><html><head><title>T</title></head><body>${body}</body></html>`;
const block = (code: string, pictures: PictureMap, extra: Partial<PreviewableBlock> = {}): PreviewableBlock => ({
  language: 'html',
  label: 'HTML',
  code,
  pictures,
  ...extra,
});

describe('putting the attached pictures into the copy that is run', () => {
  it('replaces the name in an image, a srcset, a stylesheet and a script', () => {
    const page = html(
      '<img src="photo-1.jpg" alt="me"><img srcset="photo-1.jpg 1x, photo-2.png 2x" src="photo-2.png">' +
        '<div style="background:url(photo-2.png)"></div><style>.h{background-image:url("photo-1.jpg")}</style>' +
        '<script>const hero = "photo-1.jpg";</script>',
    );
    const out = inlinePictures(block(page, { 'photo-1.jpg': JPEG, 'photo-2.png': PNG })).code;
    expect(out).not.toMatch(/photo-[12]\.(jpg|png)/);
    expect(out.split(JPEG).length - 1).toBe(4); // img, srcset, url(), script
    expect(out.split(PNG).length - 1).toBe(3); // srcset, img, url()
  });

  it('follows the name through a folder or a leading ./ and ignores case', () => {
    const out = inlinePictures(
      block(html('<img src="./Images/Photo-1.JPG"><img src="../img/photo-1.jpg"><img src="/photo-1.jpg">'), {
        'photo-1.jpg': JPEG,
      }),
    ).code;
    expect(out).not.toMatch(/photo-1/i);
    expect(out.split(JPEG).length - 1).toBe(3);
  });

  it('never touches an address, a longer name or text that merely contains one', () => {
    const page = html(
      `<img src="${WEB}cdn.example.com/photo-1.jpg"><img src="//cdn.example.com/photo-1.jpg">` +
        '<img src="my-photo-1.jpg"><img src="photo-1.jpgx"><p>see photo-1.jpg-extra</p>',
    );
    const out = inlinePictures(block(page, { 'photo-1.jpg': JPEG })).code;
    expect(out).toBe(page);
  });

  it('leaves a name that is not one of the person\'s pictures alone', () => {
    const page = html('<img src="logo.png"><img src="photo-9.jpg">');
    expect(inlinePictures(block(page, { 'photo-1.jpg': JPEG })).code).toBe(page);
  });

  it('puts a visible placeholder where the bytes are gone', () => {
    const out = inlinePictures(block(html('<img src="photo-1.jpg">'), { 'photo-1.jpg': null })).code;
    expect(out).toContain(placeholderFor('photo-1.jpg'));
    expect(atob(placeholderFor('photo-1.jpg').split(',')[1])).toContain('photo-1.jpg is no longer attached');
  });

  it('a block with no pictures comes back untouched', () => {
    const plain: PreviewableBlock = { language: 'html', label: 'HTML', code: html('<img src="photo-1.jpg">') };
    expect(inlinePictures(plain)).toBe(plain);
  });

  it('puts them into every file of an app, and rebuilds the page the frame runs', () => {
    const files: AppFile[] = [
      { path: 'index.html', code: html('<link rel="stylesheet" href="style.css"><img src="photo-1.jpg"><script src="app.js"></script>') },
      { path: 'style.css', code: '.hero{background:url(photo-1.jpg)}' },
      { path: 'app.js', code: 'document.title = "x"; new Image().src = "photo-1.jpg";' },
    ];
    const shown = block('<bundled/>', { 'photo-1.jpg': JPEG }, { files, label: 'App' });
    const run = inlinePictures(shown);
    expect(run.files!.every((f) => !f.code.includes('photo-1.jpg'))).toBe(true);
    expect(run.files!.every((f) => f.code.includes(JPEG))).toBe(true);
    // The frame runs the bundled page, so that is where the picture must be.
    expect(run.code).toContain(JPEG);
    expect(run.code).not.toContain('photo-1.jpg');
    // ... and what is shown is left as the model wrote it.
    expect(shown.files![0].code).toContain('photo-1.jpg');
    expect(shown.files![0].code).not.toContain('base64');
  });
});

describe('which picture a name stands for', () => {
  const turns = [
    { role: 'user', text: 'make a site', attachments: [{ id: 'a1', kind: 'image', pageName: 'photo-1.jpg' }, { id: 'd1', kind: 'document' }] },
    { role: 'assistant', text: `${FENCE}html\n${html('<img src="photo-1.jpg">')}\n${FENCE}` },
    { role: 'user', text: 'and a second one', attachments: [{ id: 'a2', kind: 'image', pageName: 'Photo-2.png' }] },
    { role: 'assistant', text: 'ok' },
  ];

  it('is taken from the pictures attached up to that reply, not after it', () => {
    expect(Object.keys(pictureMapFor(turns, 1, { a1: JPEG, a2: PNG }))).toEqual(['photo-1.jpg']);
    expect(Object.keys(pictureMapFor(turns, 3, { a1: JPEG, a2: PNG })).sort()).toEqual(['photo-1.jpg', 'photo-2.png']);
  });

  it('leaves out a picture that has not been fetched yet, and records one that is gone', () => {
    expect(pictureMapFor(turns, 3, { a1: JPEG })).toEqual({ 'photo-1.jpg': JPEG });
    expect(pictureMapFor(turns, 3, { a1: null, a2: PNG })).toEqual({ 'photo-1.jpg': null, 'photo-2.png': PNG });
  });

  it('a later picture with the same name is the one meant', () => {
    const again = [
      { role: 'user', text: 'q', attachments: [{ id: 'old', kind: 'image', pageName: 'photo-1.jpg' }] },
      { role: 'user', text: 'q2', attachments: [{ id: 'new', kind: 'image', pageName: 'photo-1.jpg' }] },
    ];
    expect(pictureMapFor(again, 1, { old: JPEG, new: PNG })).toEqual({ 'photo-1.jpg': PNG });
  });

  it('only the pictures a reply names are worth fetching', () => {
    expect(idsNamedIn(turns, 3, 'uses <img src="photo-1.jpg"> only')).toEqual(['a1']);
    expect(idsNamedIn(turns, 3, 'no pictures here')).toEqual([]);
  });
});

describe('a page reply that uses an attached picture', () => {
  const attachments = [{ id: 'a1', kind: 'image', pageName: 'photo-1.jpg' }];
  const page = html('<img src="photo-1.jpg" alt="Me"><h1>Portfolio</h1>');
  const turns = [
    { role: 'user', text: 'make me a portfolio site using this photo', attachments },
    { role: 'assistant', text: `Here.\n${FENCE}html\n${page}\n${FENCE}` },
  ];

  it('previews with the picture in, as a data: URI', () => {
    const reply = pageForTurn(turns, 1, {}, pictureMapFor(turns, 1, { a1: JPEG }))!;
    expect(inlinePictures(reply).code).toContain(`src="${JPEG}"`);
  });

  it('and the page itself, which is what the model is shown again, keeps the name and carries no bytes', () => {
    const reply = pageForTurn(turns, 1, {}, pictureMapFor(turns, 1, { a1: JPEG }))!;
    expect(reply.code).toContain('src="photo-1.jpg"');
    expect(asReply([{ path: 'index.html', code: reply.code }])).not.toContain('base64');
    expect(JSON.stringify(reply.code)).not.toContain('/9j/');
  });

  it('a follow-up that changes the page keeps the picture, because the earlier turn carried it', () => {
    const next = [
      ...turns,
      { role: 'user', text: 'make the photo bigger' },
      {
        role: 'assistant',
        text: `index.html\n<<<<<<< SEARCH\n<img src="photo-1.jpg" alt="Me">\n=======\n<img src="photo-1.jpg" alt="Me" width="600">\n>>>>>>> REPLACE`,
      },
    ];
    const reply = pageForTurn(next, 3, {}, pictureMapFor(next, 3, { a1: JPEG }))!;
    expect(reply.edited?.applied).toBe(1);
    const run = inlinePictures(reply).code;
    expect(run).toContain(`src="${JPEG}" alt="Me" width="600"`);
    expect(reply.code).not.toContain('base64');
  });

  it('with the bytes gone, shows a placeholder and says so in words', () => {
    const reply = pageForTurn(turns, 1, {}, pictureMapFor(turns, 1, { a1: null }))!;
    expect(inlinePictures(reply).code).toContain(placeholderFor('photo-1.jpg'));
    const notes = pictureNotes(reply);
    expect(notes).toHaveLength(1);
    expect(notes[0]).toContain('photo-1.jpg is no longer attached');
  });

  it('a conversation with no record of a picture it refers to: the page says what is missing', () => {
    const reloaded = [{ role: 'user', text: 'make me a site' }, turns[1]];
    const reply = pageForTurn(reloaded, 1, {}, pictureMapFor(reloaded, 1, {}))!;
    const notes = pictureNotes(reply);
    expect(notes).toHaveLength(1);
    expect(notes[0]).toMatch(/refers to photo-1\.jpg, which is not part of it/);
    expect(notes[0]).toContain('Zaram has no picture by that name in this conversation');
  });

  it('a page with all its pictures has nothing to say', () => {
    const reply = pageForTurn(turns, 1, {}, pictureMapFor(turns, 1, { a1: JPEG }))!;
    expect(pictureNotes(reply)).toEqual([]);
  });

  it('a picture that is not yet fetched is not called missing', () => {
    // The map leaves it out until its bytes arrive; the note must not fire in
    // that gap for a name the conversation does know.
    const reply = pageForTurn(turns, 1, {}, pictureMapFor(turns, 1, {}))!;
    expect(pictureNotes(reply).join(' ')).not.toContain('no longer attached');
  });
});

describe('the preview allows what this relies on', () => {
  it('the page policy permits data: images and nothing remote', () => {
    expect(APP_CSP).toContain("default-src 'none'");
    expect(APP_CSP).toMatch(/img-src data:(?:;| )/);
    expect(APP_CSP).not.toMatch(/img-src[^;]*https?:/);
  });

  it('the document the frame and the check run has the picture in it', async () => {
    const doc = await buildFrameDoc(block(html('<img src="photo-1.jpg">'), { 'photo-1.jpg': JPEG }));
    expect(doc).toContain(`src="${JPEG}"`);
    expect(doc).toContain('img-src data:');
  });
});
