import { describe, expect, it } from 'vitest';
import { bundleApp, extractAppFiles, normalisePath, stuckLoopIn } from './appFiles';
import { findStuckLoop } from './previewableCode';
import guidance from '../../../backend/core/page_guidance.py?raw';

const FENCE = '```';
const block = (info: string, code: string) => `${FENCE}${info}\n${code}\n${FENCE}\n`;

describe('reading which file is which', () => {
  const html = '<!DOCTYPE html><html><head><link rel="stylesheet" href="style.css"></head><body><script src="game.js"></script></body></html>';

  it('reads a name on the fence line', () => {
    const files = extractAppFiles(
      block('html index.html', html) + block('css style.css', 'body{}') + block('js game.js', 'var a=1'),
    );
    expect(files?.map((f) => f.path)).toEqual(['index.html', 'style.css', 'game.js']);
  });

  it('reads a name written as the first line of the block, and drops that line', () => {
    const files = extractAppFiles(
      block('html', `<!-- index.html -->\n${html}`) + block('js', '// game.js\nvar a=1'),
    );
    expect(files?.map((f) => f.path)).toEqual(['index.html', 'game.js']);
    expect(files?.[1].code).toBe('var a=1');
  });

  it('reads a name written on the line above the block', () => {
    const files = extractAppFiles(
      `**index.html**\n\n${block('html', html)}\n### \`game.js\`\n${block('javascript', 'var a=1')}`,
    );
    expect(files?.map((f) => f.path)).toEqual(['index.html', 'game.js']);
  });

  it('is not an app with one file, or with no page among them', () => {
    expect(extractAppFiles(block('html index.html', html))).toBeNull();
    expect(extractAppFiles(block('js a.js', '1') + block('css b.css', '2'))).toBeNull();
    expect(extractAppFiles(block('html', html) + block('js', 'var a=1'))).toBeNull();
  });

  it('keeps the later block when a file is written twice', () => {
    const files = extractAppFiles(
      block('html index.html', html) + block('js game.js', 'old') + block('js game.js', 'new'),
    );
    expect(files?.find((f) => f.path === 'game.js')?.code).toBe('new');
  });

  it('reads a fence that is still being written', () => {
    const text = block('html index.html', html) + `${FENCE}js game.js\nvar a=`;
    expect(extractAppFiles(text)?.map((f) => f.path)).toEqual(['index.html', 'game.js']);
  });
});

describe('joining the files into one page', () => {
  it('inlines the stylesheet and a classic script', () => {
    const out = bundleApp([
      { path: 'index.html', code: '<html><head><link rel="stylesheet" href="./style.css"></head><body><script src="game.js"></script></body></html>' },
      { path: 'style.css', code: 'body{color:red}' },
      { path: 'game.js', code: 'window.ran = 1;' },
    ]);
    expect(out?.html).toContain('<style>\nbody{color:red}\n</style>');
    expect(out?.html).toContain('window.ran = 1;');
    expect(out?.html).not.toContain('src="game.js"');
    expect(out?.modules).toBe(false);
  });

  it('moves a deferred script to the end of the body, where it was going to run', () => {
    const out = bundleApp([
      { path: 'index.html', code: '<html><head><script src="g.js" defer></script></head><body><canvas id="c"></canvas></body></html>' },
      { path: 'g.js', code: 'document.getElementById("c")' },
    ])!;
    expect(out.html.indexOf('<canvas')).toBeLessThan(out.html.indexOf('document.getElementById'));
  });

  it('serves modules through one import map with bare names for relative imports', () => {
    const out = bundleApp([
      { path: 'index.html', code: '<html><head></head><body><script type="module" src="main.js"></script></body></html>' },
      { path: 'main.js', code: "import { make } from './src/world.js';\nmake();" },
      { path: 'src/world.js', code: "import { n } from '../util.js';\nexport const make = () => n;" },
      { path: 'util.js', code: 'export const n = 1;' },
    ])!;
    expect(out.modules).toBe(true);
    expect(out.html).toContain('<script type="importmap">');
    // One map, ahead of the first module script.
    expect(out.html.match(/type="importmap"/g)).toHaveLength(1);
    expect(out.html.indexOf('importmap')).toBeLessThan(out.html.indexOf('type="module"'));
    const map = JSON.parse(/<script type="importmap">([\s\S]*?)<\/script>/.exec(out.html)![1]).imports as Record<string, string>;
    expect(Object.keys(map).sort()).toEqual(['zaram-app/main.js', 'zaram-app/src/world.js', 'zaram-app/util.js']);
    const world = decodeURIComponent(map['zaram-app/src/world.js'].split(',')[1]);
    expect(world).toContain("from 'zaram-app/util.js'");
    expect(world).not.toContain('../util.js');
  });

  it('lets two modules import each other', () => {
    const out = bundleApp([
      { path: 'index.html', code: '<html><body><script type="module" src="a.js"></script></body></html>' },
      { path: 'a.js', code: "import './b.js'; export const a = 1;" },
      { path: 'b.js', code: "import './a.js'; export const b = 2;" },
    ]);
    expect(out?.modules).toBe(true);
  });

  it('merges into a page\'s own import map instead of adding a second', () => {
    const out = bundleApp([
      { path: 'index.html', code: '<html><head><script type="importmap">{"imports":{"three":"https://x/three.js"}}</script></head><body><script type="module" src="main.js"></script></body></html>' },
      { path: 'main.js', code: "import * as T from 'three'; import './a.js';" },
      { path: 'a.js', code: 'export {}' },
    ])!;
    expect(out.html.match(/type="importmap"/g)).toHaveLength(1);
    const map = JSON.parse(/<script type="importmap">([\s\S]*?)<\/script>/.exec(out.html)![1]).imports as Record<string, string>;
    expect(map.three).toBe('https://x/three.js');
    expect(map['zaram-app/a.js']).toBeDefined();
  });

  it('leaves a reference to something that is not in the reply alone', () => {
    const remote = ['https:', '', 'cdn.example', 'x.js'].join('/');
    const tag = `<script src="${remote}"></script><script src="missing.js"></script>`;
    const out = bundleApp([
      { path: 'index.html', code: `<html><body>${tag}</body></html>` },
      { path: 'a.js', code: '1' },
    ]);
    expect(out?.html).toContain(tag);
  });

  it('finds a file by name when the label and the reference disagree about the folder', () => {
    const out = bundleApp([
      { path: 'index.html', code: '<html><body><script src="game.js"></script></body></html>' },
      { path: 'js/game.js', code: 'window.found = 1;' },
    ]);
    expect(out?.html).toContain('window.found = 1;');
  });

  it('does not let a script end the tag it is written into', () => {
    const out = bundleApp([
      { path: 'index.html', code: '<html><body><script src="a.js"></script></body></html>' },
      { path: 'a.js', code: 'var s = "</script><b>";' },
    ])!;
    expect(out.html).not.toContain('"</script><b>"');
  });
});

describe('paths', () => {
  it('never climbs above the root', () => {
    expect(normalisePath('../../a/./b/../c.js')).toBe('a/c.js');
  });
});

describe('a loop that never ends, in any of the files', () => {
  it('names the file it is in', () => {
    const hit = stuckLoopIn(
      [
        { path: 'index.html', code: '<html></html>' },
        { path: 'src/world.js', code: 'ok();\nfor (let i = 0; i < 16; i) { draw(i); }' },
      ],
      findStuckLoop,
    );
    expect(hit?.file).toBe('src/world.js');
    expect(hit?.line).toBe(2);
  });
});

describe('the labels the guidance asks models to write', () => {
  it('are the ones this reads', () => {
    // One contract in two languages: the backend tells a model how to name its
    // files, and this reads them. Taken from the guidance itself so neither can
    // drift from the other.
    const text = guidance;
    const labels = [...text.matchAll(/```([a-z]+) ([\w/.]+\.[a-z]+)/g)].map((m) => [m[1], m[2]]);
    expect(labels.length).toBeGreaterThanOrEqual(4);
    const reply = labels
      .map(([lang, name]) => block(`${lang} ${name}`, lang === 'html' ? '<html><body></body></html>' : 'x'))
      .join('');
    const files = extractAppFiles(reply);
    expect(files?.map((f) => f.path)).toEqual(labels.map(([, name]) => name));
  });
});
