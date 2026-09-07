'use strict';

/**
 * Spell checking, and the reason it is not simply left switched on.
 *
 * **Chromium's spellchecker was already enabled and already did nothing.**
 * `webPreferences.spellcheck` defaults to `true`, and this machine's own
 * Chromium preferences record `spellcheck.dictionaries: ["en-US"]` — so the
 * feature was on, configured, and asking for a language. What it had never had
 * is a dictionary: there was no `Dictionaries` directory under the user data
 * path, so every word was unknown, nothing was misspelled, and the composer
 * looked like an app without spell check. Reported by the maintainer on
 * 7 September 2026 as *"it doesn't have a spell check"* — exactly right about
 * the symptom, and pointing at a missing 441 KB file rather than a missing
 * feature.
 *
 * **Where Chromium would get that file is the problem.** On Windows and Linux
 * Electron fetches a Hunspell `.bdic` from Google's CDN — `redirector.gvt1.com`
 * — the first time a spellcheckable field is focused. That is a network call
 * carrying the user's address, made by Chromium, on a schedule nothing here
 * chose, and `EgressGate` cannot see it because it never passes through the
 * backend. It is the same class as the `webkitSpeechRecognition` route
 * `check-no-cloud-speech.mjs` bans, and rule 7g is unambiguous: no network call
 * before the user has consented to one.
 *
 * So the dictionary is **served from this machine**. `scripts/fetch-dictionary.mjs`
 * downloads it once, at build time, on the maintainer's machine; it is committed;
 * and at runtime a loopback server hands it to Chromium.
 * `setSpellCheckerDictionaryDownloadURL` is pointed at that server, so the
 * request Chromium insists on making is answered locally and no packet leaves.
 * With no bundled file the same setting points at a dead loopback port instead,
 * which fails immediately — spell check stays off, and still nothing is sent.
 * Asserting the quarantine rather than describing it is the lesson the
 * DuckDuckGo fix cost; `test/spellcheck.test.js` is where it is asserted.
 *
 * **Serving rather than copying is what makes it survive an Electron upgrade.**
 * Chromium asks for `<language>-<version>.bdic`, where the version tracks its
 * own format revision, and it looks for exactly that name before downloading.
 * A file copied into place under a guessed name would be ignored the moment
 * Electron bumped — silently, with no squiggles and nothing in a log. The
 * server answers whatever name is asked, so the version in the committed
 * filename is a download detail and never a contract.
 *
 * macOS needs none of this: Electron uses the operating system's own
 * spellchecker there, no `.bdic` and no download, so the server is never
 * started and the setting does not exist to be set.
 */

const fs = require('fs');
const http = require('http');
const path = require('path');

/**
 * A loopback address with nothing behind it, used when there is nothing to serve.
 *
 * Port 1 is reserved and never listened on, so Chromium's fetch fails
 * immediately and locally rather than hanging. The path segment is there so
 * that a stray entry in a log explains itself rather than looking like a port
 * scan.
 */
const FUSED_DOWNLOAD_URL = 'http://127.0.0.1:1/zaram-no-dictionary-download/';

/** The one language shipped. A second is a second file, not a code change. */
const LANGUAGE = 'en-US';

/** Where the committed dictionary lives, relative to this file. */
const BUNDLE_DIR = path.join(__dirname, 'assets', 'dictionaries');

/**
 * Where Chromium keeps the dictionary once it has one.
 *
 * @param {string} userDataPath
 * @returns {string}
 */
function dictionaryDir(userDataPath) {
  return path.join(userDataPath, 'Dictionaries');
}

/**
 * The committed dictionary, or `null` when none has been fetched.
 *
 * @param {string} [dir]
 * @returns {string | null}
 */
function bundledDictionary(dir = BUNDLE_DIR) {
  let files = [];
  try {
    files = fs.readdirSync(dir);
  } catch {
    return null;
  }
  const found = files.find((name) => name.startsWith(LANGUAGE) && name.endsWith('.bdic'));
  return found ? path.join(dir, found) : null;
}

/**
 * Whether spell check will work, and what to say when it will not.
 *
 * Three-valued in the same way `vram_bytes` is: macOS needing no dictionary is
 * not the same answer as Windows having none, and a caller that flattened the
 * two would tell a Mac user to install something they do not need.
 *
 * @param {{ userDataPath: string, platform?: string, bundle?: string | null }} options
 * @returns {{ supported: boolean, present: boolean, reason: string }}
 */
function dictionaryStatus({ userDataPath, platform = process.platform, bundle }) {
  if (platform === 'darwin') {
    return {
      supported: true,
      present: true,
      reason: 'macOS spell checks with the system dictionary; nothing to install',
    };
  }

  const bundled = bundle === undefined ? bundledDictionary() : bundle;
  if (bundled) {
    return {
      supported: true,
      present: true,
      reason: `serving ${path.basename(bundled)} over loopback`,
    };
  }

  let files = [];
  try {
    files = fs.readdirSync(dictionaryDir(userDataPath));
  } catch {
    files = [];
  }
  const installed = files.some((name) => name.startsWith(LANGUAGE) && name.endsWith('.bdic'));
  return {
    supported: true,
    present: installed,
    reason: installed
      ? 'a dictionary is already in the user data directory'
      : `no ${LANGUAGE} dictionary bundled — spell check is off, and Zaram will not fetch one. `
        + 'Run: node scripts/fetch-dictionary.mjs (441 KB, one time)',
  };
}

/**
 * Serve one dictionary file on loopback, for whatever name Chromium asks for.
 *
 * Binds to 127.0.0.1 and to port 0, so the operating system picks a free port
 * and nothing is published on another interface. Resolves `null` rather than
 * rejecting if it cannot listen: spell check is worth a window, and a window
 * that failed to open because a dictionary server could not bind would be a far
 * worse bug than the one being fixed.
 *
 * @param {{ file: string, logger?: import('./types').Logger }} options
 * @returns {Promise<{ url: string, port: number, close: () => void } | null>}
 */
function startDictionaryServer({ file, logger }) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      // Any `.bdic` request is answered with the one file there is. Chromium
      // only ever asks for the language it was given, so there is nothing to
      // route between — and matching on the extension is what makes the
      // version in the name irrelevant.
      if (!req.url || !req.url.endsWith('.bdic')) {
        res.writeHead(404);
        res.end();
        return;
      }
      let bytes;
      try {
        bytes = fs.readFileSync(file);
      } catch (error) {
        if (logger) logger.warn('dictionary unreadable', { error: String(error) });
        res.writeHead(404);
        res.end();
        return;
      }
      res.writeHead(200, {
        'Content-Type': 'application/octet-stream',
        'Content-Length': bytes.length,
      });
      res.end(bytes);
    });

    server.on('error', (error) => {
      if (logger) logger.warn('dictionary server did not start', { error: String(error) });
      resolve(null);
    });

    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      const port = typeof address === 'object' && address ? address.port : 0;
      if (!port) {
        resolve(null);
        return;
      }
      // Chromium appends the filename, so the trailing slash is required.
      resolve({
        url: `http://127.0.0.1:${port}/`,
        port,
        close: () => {
          try {
            server.close();
          } catch {
            /* a server that will not close is not worth a crash on quit */
          }
        },
      });
    });
  });
}

/**
 * Point a session's spellchecker at this machine and away from the network.
 *
 * Every call is guarded, because a window that failed to open because spell
 * checking could not be configured would be worse than no spell check.
 *
 * @param {import('electron').Session} session
 * @param {{
 *   userDataPath: string,
 *   logger?: import('./types').Logger,
 *   platform?: string,
 *   bundle?: string | null,
 * }} options
 * @returns {Promise<{ supported: boolean, present: boolean, reason: string, url: string, close: (() => void) | null }>}
 */
async function configureSpellChecker(
  session,
  { userDataPath, logger, platform = process.platform, bundle },
) {
  const bundled = bundle === undefined ? bundledDictionary() : bundle;
  const status = dictionaryStatus({ userDataPath, platform, bundle: bundled });

  let served = null;
  if (bundled && platform !== 'darwin') {
    served = await startDictionaryServer({ file: bundled, logger });
  }
  const url = served ? served.url : FUSED_DOWNLOAD_URL;

  // The download URL first, and before the language — setting a language is
  // what sends Chromium looking, so the order is the guarantee rather than a
  // style choice. Absent on macOS, where the method does not exist because the
  // download does not either.
  if (typeof session.setSpellCheckerDictionaryDownloadURL === 'function') {
    try {
      session.setSpellCheckerDictionaryDownloadURL(url);
    } catch (error) {
      if (logger) logger.warn('could not set the dictionary source', { error: String(error) });
    }
  }

  try {
    if (typeof session.setSpellCheckerLanguages === 'function') {
      session.setSpellCheckerLanguages([LANGUAGE]);
    }
  } catch (error) {
    if (logger) logger.warn('could not set the spellchecker language', { error: String(error) });
  }

  if (logger) logger.info('spellcheck', { ...status, url });
  return { ...status, url, close: served ? served.close : null };
}

/**
 * The menu items for a word Chromium marked wrong, or none.
 *
 * Pure but for the callbacks handed in, which is the point: the contents of the
 * menu can be asserted without an Electron process, and `contextMenu.js` keeps
 * its one job of putting a menu on screen. The same split the measurement tests
 * make between the arithmetic and the GPU.
 *
 * **`misspelledWord` is empty unless a dictionary is loaded**, so with none this
 * returns nothing and the menu is exactly what it was before spell check
 * existed. That is the degradation this needs: a missing dictionary makes the
 * product quieter, never broken.
 *
 * @param {{ isEditable?: boolean, misspelledWord?: string, dictionarySuggestions?: string[] }} params
 * @param {{ replace?: (word: string) => void, addWord?: (word: string) => void, logger?: import('./types').Logger }} handlers
 * @returns {Array<object>}
 */
function spellingMenuItems(params, { replace, addWord, logger } = {}) {
  if (!params || !params.isEditable || !params.misspelledWord) return [];

  const items = [];
  const suggestions = params.dictionarySuggestions || [];
  for (const suggestion of suggestions) {
    items.push({
      label: suggestion,
      // Chromium's own replacement, which keeps the caret, the undo stack and
      // the selection right. Setting the field's value from here would lose all
      // three, and would have to know which field it was.
      click: () => {
        try {
          if (replace) replace(suggestion);
        } catch (error) {
          if (logger) logger.warn('replace misspelling failed', { error: String(error) });
        }
      },
    });
  }

  if (!suggestions.length) {
    // Disabled rather than absent. A word Chromium marked wrong and has nothing
    // to offer for is a real state, and saying so is what stops the menu looking
    // as though it forgot.
    items.push({ label: 'No suggestions', enabled: false });
  }

  items.push({ type: 'separator' });
  items.push({
    label: 'Add to dictionary',
    click: () => {
      try {
        if (addWord) addWord(params.misspelledWord);
      } catch (error) {
        if (logger) logger.warn('add to dictionary failed', { error: String(error) });
      }
    },
  });
  return items;
}

module.exports = {
  configureSpellChecker,
  spellingMenuItems,
  dictionaryStatus,
  dictionaryDir,
  bundledDictionary,
  startDictionaryServer,
  FUSED_DOWNLOAD_URL,
  LANGUAGE,
};
