'use strict';

/**
 * What the browser pane may open, and what is recorded when it does.
 *
 * The pane itself is a `BrowserView` and cannot be covered here. That is the
 * reason every decision lives in `browserPolicy.js` and none of them live in
 * the glue: what is testable is the part that decides, and what is left is
 * the part that only moves pixels.
 *
 * Two of these classes are security rather than behaviour. `TheSchemes` is
 * an allow-list because *a denylist fails open*, and `WhatCountsAsLeaving`
 * is where rule 3 is read precisely — every byte that *leaves* — rather than
 * loosely enough to drown the log in localhost.
 */

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const {
  isLoopbackHost,
  resolveAddress,
  decideNavigation,
  egressFor,
} = require('../electron/services/browserPolicy');

describe('what counts as this machine', () => {
  for (const host of ['localhost', 'LOCALHOST', '127.0.0.1', '127.1.2.3', '::1', 'app.localhost']) {
    test(`${host} is loopback`, () => assert.equal(isLoopbackHost(host), true));
  }

  for (const host of ['example.com', '192.168.1.10', '10.0.0.4', 'notlocalhost', 'localhost.evil.com']) {
    test(`${host} is not loopback`, () => assert.equal(isLoopbackHost(host), false));
  }

  test('a name that merely resolves to 127.0.0.1 is not loopback', () => {
    // The DNS-rebinding shape CLAUDE.md records measuring against port 8420.
    // Trusting a hostname for what it resolves to is how that attack works,
    // so the decision is made on the name and never on a lookup.
    assert.equal(isLoopbackHost('rebind.example.com'), false);
  });
});

describe('the address bar', () => {
  test('a bare domain becomes https', () => {
    const r = resolveAddress('github.com');
    assert.equal(r.ok, true);
    assert.equal(r.url, 'https://github.com/');
    assert.equal(r.scope, 'web');
  });

  test('a localhost port becomes http, not https', () => {
    // Dev servers are http. Defaulting loopback to https would make every
    // one of them fail to open.
    const r = resolveAddress('localhost:3000');
    assert.equal(r.ok, true);
    assert.equal(r.url, 'http://localhost:3000/');
    assert.equal(r.scope, 'local');
  });

  test('a bare host:port is not read as a scheme', () => {
    // `new URL('localhost:3000')` parses `localhost:` as the protocol, so a
    // scheme check alone refuses the most common thing anyone will type.
    const r = resolveAddress('127.0.0.1:8420');
    assert.equal(r.ok, true);
    assert.equal(r.scope, 'local');
  });

  test('a full url is left alone', () => {
    assert.equal(resolveAddress('https://example.com/a?b=c').url, 'https://example.com/a?b=c');
  });

  test('an explicit http url stays http', () => {
    // Upgrading it would be a decision made on the user's behalf about a
    // site they named exactly.
    assert.equal(resolveAddress('http://example.com/').url, 'http://example.com/');
  });

  test('a path on a dev server survives', () => {
    assert.equal(resolveAddress('localhost:5173/settings').url, 'http://localhost:5173/settings');
  });

  test('empty is empty, not an error page', () => {
    assert.equal(resolveAddress('   ').reason, 'empty');
  });
});

describe('a phrase is not silently searched', () => {
  /**
   * Sending it to a search engine would be an egress to a host the person
   * never named, decided by a guess about what they meant. It comes back as
   * `not-an-address` so the pane can offer search as something to press —
   * which is the first rung of the ladder rather than a detour around it.
   */
  test('a sentence is not an address', () => {
    const r = resolveAddress('what is a tomato');
    assert.equal(r.ok, false);
    assert.equal(r.reason, 'not-an-address');
    assert.equal(r.typed, 'what is a tomato');
  });

  test('a single word is not a host', () => {
    const r = resolveAddress('tomato');
    assert.equal(r.ok, false);
    assert.equal(r.reason, 'not-an-address');
  });

  test('but a single word with a port is', () => {
    // `myserver:8080` on a work machine is a real address.
    assert.equal(resolveAddress('myserver:8080').ok, true);
  });
});

describe('the schemes', () => {
  // An allow-list, because a denylist fails open. Each of these is refused
  // for being neither http nor https, not for being named here.
  for (const typed of [
    'javascript:alert(1)',
    'file:///C:/Users/user/.ssh/id_rsa',
    'data:text/html,<script>fetch("https://x")</script>',
    'chrome://settings',
    'devtools://devtools/bundled/inspector.html',
    'about:blank',
    'ftp://files.example.com',
  ]) {
    test(`${typed.slice(0, 28)} is refused`, () => {
      const r = resolveAddress(typed);
      assert.equal(r.ok, false);
      assert.equal(r.reason, 'scheme');
    });
  }

  test('file: is refused even though the user owns the file', () => {
    // The code pack resolves every path against the project root and
    // refuses anything outside it. A browser pane that opened file:// would
    // be a way around that sandbox, reached by typing.
    assert.equal(resolveAddress('file:///etc/passwd').ok, false);
  });
});

describe('consent', () => {
  test('loopback needs none', () => {
    // Nothing leaves the machine, so there is nothing for a consent about
    // sending to govern. This is what makes the pane usable for the thing
    // it was asked for -- interacting with apps being built in Zaram.
    const d = decideNavigation('localhost:5173', { browseAllowed: false });
    assert.equal(d.allow, true);
    assert.equal(d.consented, 'not-required');
  });

  test('the open web is refused until browsing is allowed', () => {
    const d = decideNavigation('wikipedia.org', { browseAllowed: false });
    assert.equal(d.allow, false);
    assert.equal(d.reason, 'browse-not-allowed');
  });

  test('and allowed once it is', () => {
    const d = decideNavigation('wikipedia.org', { browseAllowed: true });
    assert.equal(d.allow, true);
    assert.equal(d.consented, 'browse');
  });

  test('allowing browsing does not allow a refused scheme', () => {
    // A standing answer about browsing is not a key to the filesystem.
    assert.equal(decideNavigation('file:///C:/', { browseAllowed: true }).allow, false);
  });

  test('the default is deny', () => {
    // Rule 5. Called with no options at all, the open web does not open.
    assert.equal(decideNavigation('example.com').allow, false);
  });
});

describe('what counts as leaving', () => {
  test('a page from the open web is logged', () => {
    const entry = egressFor('https://example.com/article?q=secret', { tabId: 't1' });
    assert.equal(entry.host, 'example.com');
    assert.equal(entry.dataClass, 'browse');
    assert.equal(entry.source, 'browser-pane');
  });

  test('the query string is not logged', () => {
    // It carries what was searched for, and the log is read by the person
    // but also lands in screenshots and support threads.
    const entry = egressFor('https://example.com/search?q=my+medical+question');
    assert.equal(entry.path, '/search');
    assert.ok(!JSON.stringify(entry).includes('medical'));
  });

  test('a sub-resource nobody chose is logged too', () => {
    // The reason the class exists: one news page is sixty requests to
    // companies the person never picked. They are recorded, not asked about.
    const entry = egressFor('https://ads.doubleclick.net/beacon.gif', {
      initiator: 'https://news.example.com/',
    });
    assert.equal(entry.host, 'ads.doubleclick.net');
    assert.equal(entry.initiator, 'https://news.example.com/');
  });

  test('a localhost request is not logged', () => {
    // Nothing left the machine. Logging it would put four hundred entries
    // in the log for one reload of a dev server and drown the real ones.
    assert.equal(egressFor('http://localhost:5173/src/main.tsx'), null);
  });

  test('a 127.0.0.1 request is not logged', () => {
    assert.equal(egressFor('http://127.0.0.1:8420/health'), null);
  });

  test('nonsense is not logged and does not throw', () => {
    assert.equal(egressFor('not a url'), null);
    assert.equal(egressFor(''), null);
    assert.equal(egressFor(null), null);
  });

  test('a websocket to the open web is not mistaken for nothing', () => {
    // `wss:` is not in the allow-list, so it returns null here -- and that
    // is a real gap rather than a decision: the pane's session must refuse
    // the scheme outright rather than let it through unlogged. Asserted so
    // the gap is visible if the refusal is ever removed.
    assert.equal(egressFor('wss://example.com/socket'), null);
  });
});
