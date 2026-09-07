'use strict';

/**
 * Spell check: the menu it offers, and the request it must never make.
 *
 * Runs in plain Node with no Electron process, which is why `spellingMenuItems`
 * lives in `spellcheck.js` rather than inside the `context-menu` handler. The
 * same split the GPU measurement tests make: the part that can be checked
 * anywhere is checked everywhere.
 */

const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');

const {
  spellingMenuItems,
  configureSpellChecker,
  dictionaryStatus,
  bundledDictionary,
  startDictionaryServer,
  FUSED_DOWNLOAD_URL,
} = require('../electron/spellcheck');

const labels = (items) => items.map((item) => item.label ?? `<${item.type}>`);

/** A word Chromium marked wrong, as `context-menu` reports one. */
const misspelled = {
  isEditable: true,
  misspelledWord: 'teh',
  dictionarySuggestions: ['the', 'ten', 'tea'],
};

/** A session that records what it was told, standing in for Electron's. */
function fakeSession() {
  const calls = [];
  return {
    calls,
    setSpellCheckerDictionaryDownloadURL: (url) => calls.push(['url', url]),
    setSpellCheckerLanguages: (langs) => calls.push(['languages', langs]),
  };
}

function tempDictionary(bytes = 'not a real dictionary') {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'zaram-dict-'));
  const file = path.join(dir, 'en-US-10-1.bdic');
  fs.writeFileSync(file, bytes);
  return { dir, file, clean: () => fs.rmSync(dir, { recursive: true, force: true }) };
}

// ---------------------------------------------------------------- the menu

test("a misspelled word offers its corrections, in Chromium's order", () => {
  const items = spellingMenuItems(misspelled, { replace() {}, addWord() {} });
  assert.deepStrictEqual(labels(items).slice(0, 3), ['the', 'ten', 'tea']);
});

test('choosing a correction asks Chromium to replace it', () => {
  const replaced = [];
  const items = spellingMenuItems(misspelled, { replace: (w) => replaced.push(w), addWord() {} });
  items[1].click();
  // Chromium's own replacement, not a value assignment: it is what keeps the
  // caret and the undo stack right, so the call must actually be made.
  assert.deepStrictEqual(replaced, ['ten']);
});

test('adding to the dictionary passes the word that was wrong', () => {
  const added = [];
  const items = spellingMenuItems(misspelled, { replace() {}, addWord: (w) => added.push(w) });
  items[items.length - 1].click();
  assert.deepStrictEqual(added, ['teh']);
});

test('a word with no suggestions says so rather than offering an empty menu', () => {
  const items = spellingMenuItems(
    { isEditable: true, misspelledWord: 'zaram', dictionarySuggestions: [] },
    { replace() {}, addWord() {} },
  );
  const row = items.find((item) => item.label === 'No suggestions');
  assert.ok(row, 'a word Chromium marked wrong and cannot fix is still a real state');
  assert.strictEqual(row.enabled, false);
});

test('with no dictionary loaded the menu is exactly what it was', () => {
  // `misspelledWord` is empty whenever Chromium has nothing to check against.
  // The product gets quieter; it does not get a broken menu.
  assert.deepStrictEqual(spellingMenuItems({ isEditable: true, misspelledWord: '' }, {}), []);
  assert.deepStrictEqual(spellingMenuItems({ isEditable: true }, {}), []);
  assert.deepStrictEqual(spellingMenuItems(null, {}), []);
});

test('a misspelling outside a text field offers nothing', () => {
  assert.deepStrictEqual(
    spellingMenuItems({ isEditable: false, misspelledWord: 'teh', dictionarySuggestions: ['the'] }, {}),
    [],
  );
});

// ------------------------------------------------- the request never made

test('with a dictionary bundled, Chromium is sent to loopback and not to Google', async () => {
  // The quarantine asserted rather than described. Chromium's default is
  // Google's CDN, fetched the first time a spellcheckable field is focused —
  // a request `EgressGate` cannot see because it never reaches the backend.
  const dict = tempDictionary();
  const session = fakeSession();
  try {
    const result = await configureSpellChecker(session, {
      userDataPath: os.tmpdir(),
      platform: 'win32',
      bundle: dict.file,
    });
    try {
      const url = new URL(result.url);
      assert.strictEqual(url.hostname, '127.0.0.1', `must stay on loopback, got ${url.hostname}`);
      assert.ok(url.port && Number(url.port) > 0, 'a real port must have been bound');
      assert.ok(result.url.endsWith('/'), 'Chromium appends the filename to this');
      assert.deepStrictEqual(session.calls[0], ['url', result.url]);
    } finally {
      if (result.close) result.close();
    }
  } finally {
    dict.clean();
  }
});

test('with no dictionary bundled, the download is fused rather than left at its default', async () => {
  const session = fakeSession();
  const result = await configureSpellChecker(session, {
    userDataPath: os.tmpdir(),
    platform: 'win32',
    bundle: null,
  });
  assert.strictEqual(result.url, FUSED_DOWNLOAD_URL);
  assert.strictEqual(new URL(result.url).hostname, '127.0.0.1');
  // Left unset, Electron would use Google's CDN. Setting it is the whole point.
  assert.deepStrictEqual(session.calls[0], ['url', FUSED_DOWNLOAD_URL]);
});

test('the source is set before a language is, because that is the order that matters', async () => {
  // Setting a language is what sends Chromium looking. Pointing it somewhere
  // afterwards would be a race rather than a guarantee.
  const session = fakeSession();
  const result = await configureSpellChecker(session, {
    userDataPath: os.tmpdir(),
    platform: 'win32',
    bundle: null,
  });
  if (result.close) result.close();
  assert.deepStrictEqual(session.calls.map(([what]) => what), ['url', 'languages']);
  assert.deepStrictEqual(session.calls[1][1], ['en-US']);
});

test('a session with no spellchecker at all does not stop a window opening', async () => {
  const status = await configureSpellChecker({}, {
    userDataPath: os.tmpdir(),
    platform: 'win32',
    bundle: null,
  });
  assert.strictEqual(typeof status.present, 'boolean');
});

// ----------------------------------------------------------- the server

test('the server answers whatever version name Chromium asks for', async () => {
  // The reason it serves rather than copies. Chromium looks for
  // `<language>-<its own format version>.bdic`, so a file copied into place
  // under the name we happened to download would be ignored the moment
  // Electron bumped — silently, with no squiggles and nothing in a log.
  const dict = tempDictionary('DICTIONARY BYTES');
  const served = await startDictionaryServer({ file: dict.file });
  try {
    assert.ok(served, 'the server must bind');
    for (const asked of ['en-US-10-1.bdic', 'en-US-3-0.bdic', 'en-US-99-9.bdic']) {
      const body = await get(`${served.url}${asked}`);
      assert.strictEqual(body.status, 200, `asked for ${asked}`);
      assert.strictEqual(body.text, 'DICTIONARY BYTES');
    }
  } finally {
    if (served) served.close();
    dict.clean();
  }
});

test('the server offers nothing but the dictionary', async () => {
  const dict = tempDictionary();
  const served = await startDictionaryServer({ file: dict.file });
  try {
    assert.strictEqual((await get(`${served.url}../../secrets`)).status, 404);
    assert.strictEqual((await get(`${served.url}`)).status, 404);
  } finally {
    if (served) served.close();
    dict.clean();
  }
});

function get(url) {
  return new Promise((resolve, reject) => {
    http
      .get(url, (res) => {
        let text = '';
        res.on('data', (chunk) => {
          text += chunk;
        });
        res.on('end', () => resolve({ status: res.statusCode, text }));
      })
      .on('error', reject);
  });
}

// ------------------------------------------------------------ the status

test('a missing dictionary is reported with the command that fixes it', () => {
  const empty = fs.mkdtempSync(path.join(os.tmpdir(), 'zaram-dict-'));
  try {
    const status = dictionaryStatus({ userDataPath: empty, platform: 'win32', bundle: null });
    assert.strictEqual(status.present, false);
    // Naming the fix without naming its cost is not a choice a user on a
    // metered connection can make — the same shape as the OCR extra.
    assert.match(status.reason, /fetch-dictionary\.mjs/);
    assert.match(status.reason, /441 KB/);
  } finally {
    fs.rmSync(empty, { recursive: true, force: true });
  }
});

test('a bundled dictionary is reported as present without touching user data', () => {
  const dict = tempDictionary();
  try {
    const status = dictionaryStatus({
      userDataPath: '/nonexistent',
      platform: 'win32',
      bundle: dict.file,
    });
    assert.strictEqual(status.present, true);
    assert.match(status.reason, /loopback/);
  } finally {
    dict.clean();
  }
});

test('macOS needs no dictionary and must not be told to install one', () => {
  // Electron uses the operating system's spellchecker there. `present: true`
  // with nothing on disk is the honest answer, and a caller that flattened the
  // two platforms would tell a Mac user to fix something that is not broken.
  const status = dictionaryStatus({ userDataPath: '/nonexistent', platform: 'darwin', bundle: null });
  assert.strictEqual(status.present, true);
  assert.match(status.reason, /system dictionary/);
});

test('the dictionary this repository ships is actually there', () => {
  // The one test that would go red if the committed file were dropped, or if
  // `scripts/fetch-dictionary.mjs` had never been run. Without it every other
  // test here passes against a product with no spell check.
  const file = bundledDictionary();
  assert.ok(file, 'no dictionary committed — run: node scripts/fetch-dictionary.mjs');
  const { size } = fs.statSync(file);
  assert.ok(size > 200_000, `${size} bytes is not a dictionary`);
});
