/**
 * The shell document, asserted.
 *
 * `index.html` is the one file no component test touches: it is not imported,
 * not type-checked, and not rendered by anything in this suite. So three
 * defects sat in it undisturbed — a 404 on every page load, a browser tab
 * reading `<!-- figma:title -->`, and a `lang` attribute holding the same
 * unsubstituted placeholder.
 *
 * All three are one class of bug: this file arrived as a Figma export and
 * nobody finished it. What makes them worth a test rather than a fix is that
 * the next export overwrites the file, and the placeholders come back.
 *
 * Read through Vite's `?raw` and `import.meta.glob` rather than `node:fs`,
 * because the frontend has no `@types/node` and `tsc --noEmit` is one of the
 * four gates. A test that fails typecheck is not cheaper than the bug.
 */
import { describe, it, expect } from 'vitest';
import html from '../index.html?raw';

//: Every file actually present in public/, keyed by path relative to this one.
//: Only the keys are read — nothing is imported, so the .vrm avatars in there
//: are listed without being loaded.
const PUBLIC_FILES = new Set(Object.keys(import.meta.glob('../public/**/*')));

describe('index.html', () => {
  it('declares an icon, so the browser does not ask for /favicon.ico', () => {
    // Without this link the browser requests /favicon.ico by default. Nothing
    // serves that path, so it 404s once per load — and a favicon request shows
    // up in neither the console nor the Resource Timing API, which is why it
    // went unexplained from 8 to 10 August 2026. The fix removes the request
    // rather than answering it.
    const link = html.match(/<link[^>]+rel=["']icon["'][^>]*>/i);
    expect(
      link,
      'no <link rel="icon"> — the browser will request /favicon.ico and get a 404',
    ).not.toBeNull();

    const href = link![0].match(/href=["']([^"']+)["']/i);
    expect(href, 'the icon link has no href').not.toBeNull();

    // A link pointing at a file that is not there is the same 404 with a
    // longer path to it, so the target is resolved on disk rather than trusted.
    const target = href![1].replace(/^\//, '');
    expect(
      PUBLIC_FILES.has(`../public/${target}`),
      `index.html points at /${target}, which is not in public/`,
    ).toBe(true);
  });

  it('has a real title and language, not the Figma placeholders', () => {
    // The tab genuinely rendered the string `<!-- figma:title -->`, which is
    // also what a bookmark and a window title would have said. `lang` is worse
    // than cosmetic: a screen reader picks its pronunciation from it.
    expect(html).not.toMatch(/figma:/);

    const title = html.match(/<title>([^<]*)<\/title>/i);
    expect(title, 'no <title>').not.toBeNull();
    expect(title![1].trim().length, 'the title is empty').toBeGreaterThan(0);

    expect(html).toMatch(/<html[^>]+lang=["'][a-z]{2}(-[A-Za-z]+)?["']/);
  });
});
