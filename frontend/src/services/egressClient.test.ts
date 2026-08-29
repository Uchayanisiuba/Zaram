/**
 * The wire shape of the egress policy calls.
 *
 * There is one thing here worth a test and it is not the happy path: **the
 * field name.** The client sends `data_class` and the backend reads
 * `data_class`, and nothing else in the stack would notice if one of them
 * changed — `tsc` checks the TypeScript side of the boundary and stops at the
 * network, and the backend's own tests post their own JSON.
 *
 * This repository has already paid for that gap once, between a dispatcher
 * writing `input_data["images"]` and an engine reading `input_data["image"]`:
 * two names for one thing, each side correct on its own, the picture sitting
 * intact on a step nobody ran. A consent field that fails the same way would
 * be quieter and worse — the grant would appear to be given and the refusal
 * would keep happening.
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';

import {
  fetchEgressPolicy,
  forgetEgressPolicy,
  setEgressPolicy,
} from './egressClient';

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    statusText: 'OK',
    json: async () => ({}),
    text: async () => '',
  });
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Indexed rather than the obvious `at(-1)`, which this project's `lib` target
 *  does not carry: `tsc --noEmit` refuses it while vitest transpiles it
 *  happily, so a green test run does not catch it. */
function lastBody(): Record<string, unknown> {
  const [, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
  return JSON.parse((init as RequestInit).body as string);
}

describe('setting a policy', () => {
  it('sends the class under the name the backend reads', () => {
    void setEgressPolicy('api.example.test', 'allow', 'image');

    expect(lastBody()).toEqual({
      host: 'api.example.test',
      mode: 'allow',
      data_class: 'image',
    });
  });

  it('defaults to the least sensitive class, not the most', () => {
    // A caller that does not say what it is sending must not be able to grant
    // permission for a photograph by omission. The other direction would be
    // safer in the abstract and would deny the ordinary chat path, which is
    // every existing call site.
    void setEgressPolicy('api.example.test', 'allow');

    expect(lastBody().data_class).toBe('prompt');
  });
});

describe('forgetting a policy', () => {
  it('forgets the whole destination when no class is named', () => {
    // An image grant left behind after the host rule was removed would be a
    // permission outliving the decision that created it — and invisible,
    // since the pane lists host rules.
    void forgetEgressPolicy('api.example.test');

    const [url] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
    expect(url).toBe('/egress/policy/api.example.test');
  });

  it('forgets one class when one is named', () => {
    void forgetEgressPolicy('api.example.test', 'image');

    const [url] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
    expect(url).toBe('/egress/policy/api.example.test?data_class=image');
  });

  it('escapes a host rather than pasting it into the path', () => {
    void forgetEgressPolicy('a host/with slashes');

    const [url] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1];
    expect(url).not.toContain('with slashes');
    expect(url).toContain('%2F');
  });
});

describe('reading the policy', () => {
  it('carries class rules across, and survives a backend that sends none', async () => {
    // The second half matters more than the first: an older backend answers
    // without the key, and a pane that reads `undefined.image` renders
    // nothing at all rather than an empty list.
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => ({
        default: 'deny',
        rules: { 'api.example.test': 'allow' },
        hosts_seen: ['api.example.test'],
        hosts_without_a_rule: [],
      }),
    });

    const withoutClasses = await fetchEgressPolicy();
    expect(withoutClasses.classRules).toEqual({});

    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => ({
        default: 'deny',
        rules: { 'api.example.test': 'allow' },
        class_rules: { 'api.example.test': { image: 'allow' } },
        hosts_seen: ['api.example.test'],
        hosts_without_a_rule: [],
      }),
    });

    const withClasses = await fetchEgressPolicy();
    expect(withClasses.classRules['api.example.test'].image).toBe('allow');
  });
});
