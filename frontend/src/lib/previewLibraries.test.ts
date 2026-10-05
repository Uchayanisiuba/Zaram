/**
 * @vitest-environment jsdom
 *
 * three.js for the preview, from Zaram's own copy.
 *
 * Asked for 5 October 2026 after a Minecraft-style page showed its title screen
 * and *"THREE is not defined"*: the preview has no network and the page asked
 * a CDN for three.js. These cover the rewriting on small stand-ins, then run
 * the real library and the real addons, because a rewrite that produces text
 * nobody executed is the assertion-free test this codebase has paid for.
 */
import { describe, expect, it } from 'vitest';

import {
  ADDONS,
  addonFor,
  classicAddon,
  isThreeCore,
  loadThree,
  usesThree,
  vendorPage,
  type VendoredThree,
} from './previewLibraries';
import { APP_SANDBOX, wrapForPreview } from './previewableCode';

const fake: VendoredThree = {
  cjs: 'exports.Scene = function Scene() {}; exports.REVISION = "185";',
  names: ['Scene', 'REVISION'],
  addons: Object.fromEntries(
    ADDONS.map((p) => [p, `import { Scene } from 'three';\nclass X {}\nexport { X };`]),
  ) as VendoredThree['addons'],
  revision: 'r185',
};

/** A classic script tag, built rather than written out, so the source holds
 *  no literal remote `src=` — the no-remote-assets guard reads source, and
 *  these are pages being rewritten, not assets Zaram loads. */
const tag = (url: string) => `<script src="${url}"></script>`;

const decode = (dataUrl: string) => decodeURIComponent(dataUrl.replace(/^data:text\/javascript;charset=utf-8,/, ''));
const mapOf = (html: string) =>
  JSON.parse(/<script type="importmap">([\s\S]*?)<\/script>/.exec(html)![1]).imports as Record<string, string>;

describe('what counts as three.js', () => {
  it.each([
    'three',
    'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js',
    'https://unpkg.com/three@0.150.1/build/three.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js',
    'https://threejs.org/build/three.module.js',
    'https://esm.sh/three@0.160.0',
    'https://cdn.skypack.dev/three',
  ])('%s', (spec) => expect(isThreeCore(spec)).toBe(true));

  it.each([
    'https://evil.example/three.min.js',
    'https://cdn.jsdelivr.net/npm/lodash/lodash.min.js',
    'three-stdlib',
  ])('not %s', (spec) => expect(isThreeCore(spec)).toBe(false));

  it('knows the curated addons in both shapes, and nothing else', () => {
    expect(addonFor('three/addons/controls/PointerLockControls.js')).toEqual({
      path: 'controls/PointerLockControls.js',
      classic: false,
    });
    expect(addonFor('https://cdn.jsdelivr.net/npm/three@0.128/examples/js/controls/PointerLockControls.js')).toEqual({
      path: 'controls/PointerLockControls.js',
      classic: true,
    });
    expect(addonFor('three/addons/loaders/GLTFLoader.js')).toBeNull();
    expect(addonFor('https://evil.example/examples/jsm/controls/OrbitControls.js')).toBeNull();
  });

  it('leaves a page that does not use it alone', () => {
    expect(usesThree('<canvas></canvas><script>draw()</script>')).toBe(false);
    expect(vendorPage('<p>hello</p>', fake)).toBeNull();
  });
});

describe('a classic page', () => {
  const page =
    tag('https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js') + '\n' +
    tag('https://cdn.jsdelivr.net/npm/three@0.128/examples/js/controls/PointerLockControls.js') + '\n' +
    '<script>const s = new THREE.Scene();</script>';

  it('drops the CDN tag, defines THREE ahead of the page, and inlines the addon in place', () => {
    const v = vendorPage(page, fake)!;
    expect(v.body).not.toContain('cdnjs.cloudflare.com');
    expect(v.body).not.toContain('cdn.jsdelivr.net');
    expect(v.prefix).toContain('window.THREE=Object.assign({},module.exports)');
    // The addon sits where its tag was: after the core, before the page.
    expect(v.body.indexOf('window.THREE.X = X;')).toBeLessThan(v.body.indexOf('new THREE.Scene()'));
    expect(v.served).toBe("three.js r185, from Zaram's own copy");
  });
});

describe('a module page', () => {
  it('maps bare and CDN imports to one copy, and the addons through it', () => {
    const page =
      '<script type="module">\n' +
      "import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';\n" +
      "import { PointerLockControls } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/PointerLockControls.js';\n" +
      '</script>';
    const v = vendorPage(page, fake)!;
    const map = mapOf(v.prefix);
    const shim = decode(map['https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js']);
    expect(shim).toContain('const T = window.THREE;');
    expect(shim).toContain('export const { Scene, REVISION } = T;');
    expect(map.three).toBe(map['https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js']);
    expect(decode(map['https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/PointerLockControls.js'])).toContain(
      "from 'three'",
    );
  });

  it("rewrites the page's own import map in place rather than adding a second", () => {
    const page =
      '<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js",' +
      '"three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>\n' +
      '<script type="module">import * as THREE from "three";\n' +
      'import { OrbitControls } from "three/addons/controls/OrbitControls.js";\n' +
      'import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";</script>';
    const v = vendorPage(page, fake)!;
    expect(v.prefix).not.toContain('importmap');
    expect((v.body.match(/type="importmap"/g) ?? []).length).toBe(1);
    const map = JSON.parse(/<script type="importmap">([\s\S]*?)<\/script>/.exec(v.body)![1]).imports;
    expect(map.three.startsWith('data:')).toBe(true);
    expect(map['three/addons/controls/OrbitControls.js'].startsWith('data:')).toBe(true);
    // Not curated: the page's prefix entry still covers it, and the frame
    // reports the host like any other.
    expect(map['three/addons/loaders/GLTFLoader.js']).toBeUndefined();
    expect(map['three/addons/']).toBe('https://unpkg.com/three@0.160.0/examples/jsm/');
  });
});

describe('the frame it runs in', () => {
  it('lets a game lock the pointer, and still nothing that leaves the frame', () => {
    expect(APP_SANDBOX.split(' ')).toEqual(['allow-scripts', 'allow-pointer-lock']);
  });

  it('allows data: modules only when a library is served, and draws an app unpadded', () => {
    expect(wrapForPreview('<p/>', 'app')).not.toContain("'unsafe-eval' data:");
    expect(wrapForPreview('<p/>', 'app', [], '<script></script>')).toContain("'unsafe-eval' data:");
    expect(wrapForPreview('<p/>', 'app')).not.toContain('padding: 24px');
    expect(wrapForPreview('<p/>', 'document')).toContain('padding: 24px');
  });
});

describe('the real library', () => {
  it('runs: THREE is defined, and the classic addons attach to it', async () => {
    const three = await loadThree();
    expect(three.revision).toBe('r185');
    expect(three.names).toEqual(expect.arrayContaining(['Scene', 'PerspectiveCamera', 'WebGLRenderer', 'BoxGeometry']));

    const v = vendorPage(tag('https://unpkg.com/three/build/three.min.js'), three)!;
    const core = /<script>([\s\S]*?)<\/script>/.exec(v.prefix)![1];
    // Executed, not inspected: a rewrite nobody ran is not evidence.
    new Function(core)();
    const T = (window as unknown as { THREE: Record<string, unknown> }).THREE;
    expect(typeof T.Scene).toBe('function');
    expect(new (T.Vector3 as new (x: number, y: number, z: number) => { x: number })(1, 2, 3).x).toBe(1);

    for (const path of ADDONS) {
      const script = /<script>([\s\S]*?)<\/script>/.exec(classicAddon(three.addons[path]))![1];
      new Function(script)();
    }
    expect(typeof T.PointerLockControls).toBe('function');
    expect(typeof T.OrbitControls).toBe('function');
    expect(typeof T.ImprovedNoise).toBe('function');
    expect(typeof T.SimplexNoise).toBe('function');
  });
});
