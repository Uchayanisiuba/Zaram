'use strict';

/**
 * What the pane asks the backend, and what it tells it.
 *
 * Driven entirely through an injected `fetch`, so the consent cache and the
 * egress batching are covered without a window, a backend, or a network.
 *
 * The class that matters most is `WhenTheBackendIsDown`. A browser whose
 * consent check fails open is a browser that opens the web when the thing
 * that was supposed to permit it is not answering — which is the one
 * condition under which a fail-open default is actually reached.
 */

const { test, describe, beforeEach } = require('node:test');
const assert = require('node:assert/strict');

const {
  createBrowserBackend,
  ANSWER_TTL_MS,
  MAX_PER_FLUSH,
} = require('../electron/services/browserBackend');

/** A fetch that answers a fixed policy and records every call. */
function fakeFetch({ browse = null, ok = true, throws = false } = {}) {
  const calls = [];
  const impl = async (url, options = {}) => {
    calls.push({ url, options, body: options.body ? JSON.parse(options.body) : null });
    if (throws) throw new Error('backend down');
    if (!ok) return { ok: false, status: 500, json: async () => ({}) };
    if (String(url).endsWith('/egress/policy')) {
      return {
        ok: true,
        json: async () => ({ class_defaults: browse ? { browse } : {} }),
      };
    }
    return { ok: true, json: async () => ({ recorded: true }) };
  };
  impl.calls = calls;
  return impl;
}

function backend(fetchImpl) {
  return createBrowserBackend({
    baseUrl: 'http://127.0.0.1:8420',
    getSecret: () => 'secret',
    logger: { warn() {} },
    fetchImpl,
  });
}

describe('the standing answer', () => {
  test('browsing is off until the policy says allow', async () => {
    const b = backend(fakeFetch({ browse: null }));
    await b.refresh();
    assert.equal(b.isBrowseAllowed(), false);
  });

  test('and on once it does', async () => {
    const b = backend(fakeFetch({ browse: 'allow' }));
    await b.refresh();
    assert.equal(b.isBrowseAllowed(), true);
  });

  test('a class default of ask is not an allow', async () => {
    const b = backend(fakeFetch({ browse: 'ask' }));
    await b.refresh();
    assert.equal(b.isBrowseAllowed(), false);
  });

  test('it is not read once per request', async () => {
    // A page is sixty requests and would be sixty round trips to answer a
    // question nobody changed in between.
    const f = fakeFetch({ browse: 'allow' });
    const b = backend(f);
    await b.refresh();
    for (let i = 0; i < 20; i += 1) b.isBrowseAllowed();
    const policyCalls = f.calls.filter((c) => String(c.url).endsWith('/egress/policy'));
    assert.equal(policyCalls.length, 1);
  });

  test('the credential goes with it', async () => {
    const f = fakeFetch({ browse: 'allow' });
    await backend(f).refresh();
    assert.equal(f.calls[0].options.headers['X-Zaram-Auth'], 'secret');
  });

  test('the cache is short enough to notice a change in Settings', () => {
    // Somebody who turns browsing on should not have to reopen the tab.
    assert.ok(ANSWER_TTL_MS <= 10_000, `${ANSWER_TTL_MS}ms is too long to wait`);
  });
});

describe('when the backend is down', () => {
  test('browsing stays off', async () => {
    // Fails closed. Rule 5's default deny has to survive the thing that
    // was going to permit it not answering.
    const b = backend(fakeFetch({ throws: true }));
    await b.refresh();
    assert.equal(b.isBrowseAllowed(), false);
  });

  test('an error response does not turn it on', async () => {
    const b = backend(fakeFetch({ ok: false }));
    await b.refresh();
    assert.equal(b.isBrowseAllowed(), false);
  });

  test('a previously granted answer is not revoked by one bad read', async () => {
    // The other direction: a momentary blip must not make a working pane
    // start refusing pages, which reads as the product being broken.
    const b = backend(fakeFetch({ browse: 'allow' }));
    await b.refresh();
    const flaky = backend(fakeFetch({ throws: true }));
    await flaky.refresh();
    assert.equal(b.isBrowseAllowed(), true);
  });

  test('a failed log write does not throw at the caller', async () => {
    // It is called from inside a request handler. A throw there stops the
    // page loading at all.
    const b = backend(fakeFetch({ throws: true }));
    b.record({ host: 'example.com', path: '/' });
    await b.flush();
  });
});

describe('what reaches the log', () => {
  test('a recorded request is posted', async () => {
    const f = fakeFetch({ browse: 'allow' });
    const b = backend(f);
    b.record({ host: 'example.com', path: '/a' });
    await b.flush();
    const posts = f.calls.filter((c) => String(c.url).endsWith('/egress/browse'));
    assert.equal(posts.length, 1);
    assert.equal(posts[0].body.host, 'example.com');
  });

  test('forty fonts from one host are one row', async () => {
    // One destination contacted. Forty identical rows make the log harder
    // to read rather than more complete.
    const f = fakeFetch();
    const b = backend(f);
    for (let i = 0; i < 40; i += 1) b.record({ host: 'fonts.gstatic.com', path: '/x.woff2' });
    await b.flush();
    assert.equal(f.calls.filter((c) => String(c.url).endsWith('/egress/browse')).length, 1);
  });

  test('different paths on one host stay separate', async () => {
    const f = fakeFetch();
    const b = backend(f);
    b.record({ host: 'example.com', path: '/a' });
    b.record({ host: 'example.com', path: '/b' });
    await b.flush();
    assert.equal(f.calls.filter((c) => String(c.url).endsWith('/egress/browse')).length, 2);
  });

  test('the page that pulled it in travels with it', async () => {
    const f = fakeFetch();
    const b = backend(f);
    b.record({ host: 'ads.doubleclick.net', path: '/b.gif', initiator: 'https://news.example.com/' });
    await b.flush();
    assert.equal(f.calls[0].body.initiator, 'https://news.example.com/');
  });

  test('a flood is capped, and the overflow is counted rather than dropped', async () => {
    // A page pulling a thousand resources is a page, not an attack -- but
    // the queue must not outrun the drain. One row saying how many is less
    // information than the rows, and is honest about being less.
    const f = fakeFetch();
    const b = backend(f);
    for (let i = 0; i < MAX_PER_FLUSH + 25; i += 1) {
      b.record({ host: `h${i}.example.com`, path: '/' });
    }
    await b.flush();
    const posts = f.calls.filter((c) => String(c.url).endsWith('/egress/browse'));
    assert.equal(posts.length, MAX_PER_FLUSH + 1);
    const overflow = posts[posts.length - 1].body;
    assert.equal(overflow.host, 'zaram.overflow');
    assert.match(overflow.path, /25-not-recorded/);
  });

  test('a record with no host is ignored', async () => {
    const f = fakeFetch();
    const b = backend(f);
    b.record({ path: '/a' });
    b.record(null);
    await b.flush();
    assert.equal(f.calls.length, 0);
  });
});
