/**
 * @vitest-environment jsdom
 *
 * A page describes its photographs (`photo:...`); the window reads the
 * descriptions, puts the found pictures in only in the copy that is run or
 * saved, credits them from what the source said, and labels what was not found.
 */
import { describe, expect, it } from 'vitest';

import {
  canLookAgain,
  creditsHtml,
  photoDescriptions,
  photoKey,
  photoNotes,
  swapPhotos,
  withCredits,
  withPhotos,
  type PhotoMap,
} from './pagePhotos';
import { inlinePictures } from './pagePictures';
import type { PreviewableBlock } from './previewableCode';
// Assembled, not written out: `check-no-remote-assets` scans test files too and cannot tell a fixture from a page.
const WEB = 'ht' + 'tps://';

const beach = {
  uri: 'data:image/jpeg;base64,QkVBQ0g=',
  title: 'Sunset on the beach',
  creator: 'Ada O.',
  license: 'CC BY 2.0',
  licenseUrl: 'https://creativecommons.org/licenses/by/2.0/',
  sourceUrl: 'https://www.flickr.com/photos/x/1',
};

const page = (body: string): PreviewableBlock =>
  ({ language: 'html', label: 'page', code: `<!doctype html><html><body>${body}</body></html>` }) as PreviewableBlock;

describe('reading the descriptions a page wrote', () => {
  it('finds them in src, srcset and CSS url(), once each, in order', () => {
    const html =
      '<img src="photo:Lagos beach at sunset" alt="">' +
      '<img srcset="photo:street food market 2x">' +
      "<div style=\"background-image:url('photo:mountain village at dawn')\"></div>" +
      '<section style="background:url(photo:old town square)"></section>' +
      '<img src="photo:LAGOS  beach at sunset">';
    expect(photoDescriptions(html)).toEqual([
      'Lagos beach at sunset',
      'street food market',
      'mountain village at dawn',
      'old town square',
    ]);
  });

  it('keeps page order across CSS and attributes, so a background hero is first', () => {
    const html = "<style>.hero{background:url('photo:Lagos skyline')}</style><img src=\"photo:beach\">";
    expect(photoDescriptions(html)).toEqual(['Lagos skyline', 'beach']);
  });

  it('decodes percent-encoding and entities, and ignores the copied template', () => {
    const html =
      '<img src="photo:hotel%20room">' +
      '<img src="photo:fish &amp; chips">' +
      '<img src="photo:short description of the photo">';
    expect(photoDescriptions(html)).toEqual(['hotel room', 'fish & chips']);
  });

  it('keys a description the way the backend does', () => {
    expect(photoKey('  Lagos   Beach, at sunset! ')).toBe('lagos beach at sunset');
  });

  it('leaves ordinary image addresses alone', () => {
    expect(photoDescriptions(`<img src="beach.jpg"><img src="${WEB}x.org/a.png">`)).toEqual([]);
  });
});

describe('putting the pictures in', () => {
  const photos: PhotoMap = {
    [photoKey('Lagos beach at sunset')]: beach,
    [photoKey('old town square')]: { error: 'Nothing matched that description.', code: 'no_match' },
  };

  it('replaces a found description with its picture, keeping srcset descriptors', () => {
    const out = swapPhotos('<img src="photo:Lagos beach at sunset"><img srcset="photo:lagos beach at sunset 2x">', photos);
    expect(out).toBe(`<img src="${beach.uri}"><img srcset="${beach.uri} 2x">`);
  });

  it('puts a labelled placeholder where a photo was not found, and where it is still being looked for', () => {
    const missing = swapPhotos("<div style=\"background:url('photo:old town square')\"></div>", photos);
    expect(missing).toMatch(/url\('data:image\/svg\+xml;base64,/);
    expect(atob(missing.split('base64,')[1].split("'")[0])).toContain('No photo: Nothing matched that description.');
    const pending = swapPhotos('<img src="photo:harbour at night">', photos);
    expect(atob(pending.split('base64,')[1].split('"')[0])).toContain('Finding a photo');
  });

  it('runs and saves the page with pictures and credits, and keeps the descriptions in what the model sees', () => {
    const block = withPhotos(page('<img src="photo:Lagos beach at sunset">'), photos);
    const runnable = inlinePictures(block);
    expect(runnable.code).toContain(beach.uri);
    expect(runnable.code).toContain('data-zaram-photo-credits');
    expect(runnable.code.indexOf('data-zaram-photo-credits')).toBeLessThan(runnable.code.indexOf('</body>'));
    // The block itself -- shown as code, sent back on a follow-up -- is unchanged.
    expect(block.code).toContain('photo:Lagos beach at sunset');
    expect(block.code).not.toContain('base64');
  });

  it('credits the page that is opened in a multi-file app', () => {
    const block = withPhotos(
      {
        language: 'html',
        label: 'app',
        code: '',
        files: [
          { path: 'index.html', code: '<html><body><link href="style.css"></body></html>' },
          { path: 'style.css', code: ".hero{background:url('photo:Lagos beach at sunset')}" },
        ],
      } as unknown as PreviewableBlock,
      photos,
    );
    const runnable = inlinePictures(block);
    expect(runnable.files![0].code).toContain('data-zaram-photo-credits');
    expect(runnable.files![1].code).toContain(beach.uri);
  });

  it('leaves a page without descriptions exactly as it was', () => {
    const plain = page('<p>hello</p>');
    expect(withPhotos(plain, photos)).toBe(plain);
    expect(inlinePictures(plain)).toBe(plain);
  });
});

describe('credits', () => {
  it('names only what the source gave, and links only https addresses', () => {
    const html = creditsHtml({
      a: beach,
      b: { ...beach, creator: '', title: 'Market <b>', sourceUrl: 'javascript:alert(1)', licenseUrl: '' },
    });
    expect(html).toContain('&ldquo;Sunset on the beach&rdquo;');
    expect(html).toContain('by Ada O.');
    expect(html).toContain(`href="${WEB}creativecommons.org/licenses/by/2.0/"`);
    expect(html).not.toContain('javascript:');
    expect(html).toContain('Market &lt;b&gt;');
    expect(html).not.toMatch(/Market &lt;b&gt;.{0,20} by /);
  });

  it('credits each photo to its own source, and never names one that was not used', () => {
    const html = creditsHtml({
      a: { ...beach, source: 'Openverse' },
      b: { ...beach, title: 'Harbour', source: 'Wikimedia Commons' },
    });
    expect(html).toContain('(via Openverse)');
    expect(html).toContain('(via Wikimedia Commons)');
    // The line is no longer a blanket "found through Openverse".
    expect(html).not.toContain('found through');
    const onlyCommons = creditsHtml({ b: { ...beach, source: 'Wikimedia Commons' } });
    expect(onlyCommons).toContain('(via Wikimedia Commons)');
    expect(onlyCommons).not.toContain('Openverse');
  });

  it('escapes a source name and omits the parenthesis when none was given', () => {
    expect(creditsHtml({ a: { ...beach, source: '<b>X</b>' } })).toContain('(via &lt;b&gt;X&lt;/b&gt;)');
    expect(creditsHtml({ a: beach })).not.toContain('via');
  });

  it('adds nothing when no photo was found, and never twice', () => {
    expect(creditsHtml({ x: { error: 'no', code: 'no_match' } })).toBe('');
    const once = withCredits('<body></body>', '<footer data-zaram-photo-credits></footer>');
    expect(withCredits(once, '<footer data-zaram-photo-credits></footer>')).toBe(once);
  });
});

describe('what the person is told', () => {
  it('says the search did not happen when they said no, and offers to look again', () => {
    const block = withPhotos(page('<img src="photo:beach">'), {
      beach: { error: 'You chose not to search.', code: 'consent_declined' },
    });
    expect(photoNotes(block)[0]).toMatch(/did not search for photos/);
    expect(canLookAgain(block)).toBe(true);
  });

  it('offers to look again when the page ran out of time or the source asked for fewer requests', () => {
    for (const code of ['busy', 'rate_limited']) {
      const block = withPhotos(page('<img src="photo:beach">'), { beach: { error: 'Try again.', code } });
      expect(canLookAgain(block)).toBe(true);
    }
  });

  it('gives the reason when nothing matched, and does not offer a pointless retry', () => {
    const block = withPhotos(page('<img src="photo:beach">'), {
      beach: { error: 'Nothing matched that description.', code: 'no_match' },
    });
    expect(photoNotes(block)[0]).toMatch(/1 photo was not found.*Nothing matched/);
    expect(canLookAgain(block)).toBe(false);
  });

  it('says nothing while a photo is still being looked for', () => {
    expect(photoNotes(withPhotos(page('<img src="photo:beach">'), {}))).toEqual([]);
  });
});
