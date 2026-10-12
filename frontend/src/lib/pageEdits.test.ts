/**
 * A page changed by the lines that change, and a loop that lost its `++`.
 *
 * 11 October 2026: a Minecraft-style game took an afternoon because every fix
 * rewrote 15,000 characters, and the first draft froze on `for(...; z)`. These
 * hold the two mechanisms that replace that: SEARCH/REPLACE edits applied to the
 * page the conversation already has, and the one loop defect with a single reading
 * repaired rather than sent back.
 */
import { describe, expect, it } from 'vitest';

import { applyEdits, asReply, extractEdits, repairLoops } from './pageEdits';
import { pageForTurn, starterNamed } from './replyPage';

const PAGE = '<!DOCTYPE html>\n<html><body>\n<script>\nconst SPEED = 4;\nfunction go() { return SPEED; }\n</script>\n</body></html>';

const edit = (search: string, replace: string, file = '') =>
  `${file ? file + '\n' : ''}\`\`\`\n<<<<<<< SEARCH\n${search}\n=======\n${replace}\n>>>>>>> REPLACE\n\`\`\``;

describe('extractEdits', () => {
  it('reads blocks and the file named above each', () => {
    const text = `Here is the fix.\n\n${edit('a', 'b', 'game.js')}\n\nAnd:\n\n${edit('c', 'd', 'style.css')}`;
    expect(extractEdits(text)).toEqual([
      { file: 'game.js', search: 'a', replace: 'b' },
      { file: 'style.css', search: 'c', replace: 'd' },
    ]);
  });

  it('takes a name on the fence line, and none for a page of one file', () => {
    const fenced = '```js game.js\n<<<<<<< SEARCH\nx\n=======\ny\n>>>>>>> REPLACE\n```';
    expect(extractEdits(fenced)[0].file).toBe('game.js');
    expect(extractEdits(edit('x', 'y'))[0].file).toBeNull();
  });

  it('finds nothing in an ordinary reply', () => {
    expect(extractEdits('```html\n<p>hi</p>\n```')).toEqual([]);
  });
});

describe('applyEdits', () => {
  const files = [{ path: 'index.html', code: PAGE }];

  it('changes only the lines named', () => {
    const out = applyEdits(files, [{ file: null, search: 'const SPEED = 4;', replace: 'const SPEED = 6;' }]);
    expect(out.applied).toBe(1);
    expect(out.failed).toEqual([]);
    expect(out.files[0].code).toBe(PAGE.replace('SPEED = 4', 'SPEED = 6'));
    expect(files[0].code).toBe(PAGE); // the base is not edited in place
  });

  it('tolerates trailing spaces and Windows line endings, and nothing looser', () => {
    const loose = applyEdits(files, [{ file: null, search: 'const SPEED = 4;   \r\nfunction go()', replace: 'X' }]);
    expect(loose.applied).toBe(1);
    const wrong = applyEdits(files, [{ file: null, search: 'const speed = 4;', replace: 'X' }]);
    expect(wrong.applied).toBe(0);
    expect(wrong.failed[0].reason).toMatch(/not in the file/);
  });

  it('names the file that does not exist, and creates one when SEARCH is empty', () => {
    const missing = applyEdits(files, [{ file: 'world.js', search: 'x', replace: 'y' }]);
    expect(missing.failed[0].reason).toMatch(/no file called world.js/);
    const added = applyEdits(files, [{ file: 'world.js', search: '', replace: 'export const W = 1;' }]);
    expect(added.files.map((f) => f.path)).toEqual(['index.html', 'world.js']);
  });
});

describe('repairLoops', () => {
  it('puts back the step the model dropped, in the direction the loop counts', () => {
    const out = repairLoops('for(let z=minZ; z<=maxZ; z){}\nfor (let i = n; i > 0; i) {}');
    expect(out.code).toContain('z<=maxZ; z++)');
    expect(out.code).toContain('i > 0; i--)');
    expect(out.repaired).toHaveLength(2);
  });

  it('leaves a loop whose body steps the counter itself, and reaches inside nested loops', () => {
    const self = 'for (let i = 0; i < n; i) { draw(i); i += 2; }';
    expect(repairLoops(self)).toEqual({ code: self, repaired: [] });
    const nested = 'for(let x=0; x<4; x++) for(let z=0; z<4; z){ put(x, z); }';
    expect(repairLoops(nested).code).toContain('z<4; z++)');
    const nestedSelf = 'for(let z=0; z<4; z) for(let y=0; y<2; y++){ z = z + 1; }';
    expect(repairLoops(nestedSelf).repaired).toEqual([]);
  });

  it('leaves every loop that already steps alone', () => {
    const fine = 'for (let x = 0; x < 9; x++) {}\nfor (let y = 0; y < 9; y += 2) {}\nfor (const k in o) {}';
    expect(repairLoops(fine)).toEqual({ code: fine, repaired: [] });
  });
});

describe('pageForTurn', () => {
  const turns = (...texts: string[]) => texts.map((text, i) => ({ role: i % 2 ? 'assistant' : 'user', text }));

  it('applies a reply of changes to the page before it', () => {
    const t = turns('make a page', '```html\n' + PAGE + '\n```', 'faster', 'Done.\n\n' + edit('const SPEED = 4;', 'const SPEED = 9;'));
    const page = pageForTurn(t, 3);
    expect(page?.code).toContain('SPEED = 9');
    expect(page?.edited).toEqual({ applied: 1, failed: [] });
  });

  it('applies changes to a named starting point', () => {
    const reply = 'Starting from: voxel-world\n\n' + edit('const SPEED = 4;', 'const SPEED = 2;');
    const page = pageForTurn(turns('build a minecraft game', reply), 1, { 'voxel-world': PAGE });
    expect(page?.code).toContain('SPEED = 2');
    expect(page?.edited?.starter).toBe('voxel-world');
  });

  it('the starting line alone is the starting point unchanged', () => {
    const page = pageForTurn(turns('build a minecraft game', 'Starting from: voxel-world\n\nIt already does all that.'), 1, {
      'voxel-world': PAGE,
    });
    expect(page?.code).toBe(PAGE);
  });

  it('has no page until the starting point has arrived', () => {
    expect(pageForTurn(turns('q', 'Starting from: voxel-world'), 1, {})).toBeNull();
  });

  it('repairs a dropped step in a page written out whole, and says so', () => {
    const broken = PAGE.replace('function go()', 'for(let i=0; i<3; i){}\nfunction go()');
    const page = pageForTurn(turns('q', '```html\n' + broken + '\n```'), 1);
    expect(page?.code).toContain('i<3; i++)');
    expect(page?.repaired).toHaveLength(1);
  });

  it('reads the starting line however it is dressed', () => {
    expect(starterNamed('**Starting from:** `voxel-world`')).toBe('voxel-world');
    expect(starterNamed('Starting from voxel-world')).toBe('voxel-world');
    expect(starterNamed('Just a reply.')).toBeNull();
  });

  it('writes the page back out as a reply the model can edit against', () => {
    expect(asReply([{ path: 'index.html', code: PAGE }])).toBe('```html\n' + PAGE + '\n```');
  });
});
