/**
 * What the character transport must not get wrong.
 *
 * The load-bearing one is the first: `undefined` and `""` are different
 * intentions, and collapsing them would make "I did not touch the manner"
 * indistinguishable from "remove my manner". Only the second is something a
 * user does on purpose, and getting it backwards silently erases a setting
 * every time an unrelated field is saved.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  CharacterError,
  downloadVoice,
  fetchCharacter,
  fetchVoiceCatalogue,
  fetchVoices,
  saveCharacter,
} from './characterClient';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** The body of the request the code under test made, parsed. */
const sentBody = (): Record<string, unknown> =>
  JSON.parse(String(fetchMock.mock.calls[fetchMock.mock.calls.length - 1][1].body));

const stored = { assistant_name: '', manner: '', voice: '', default_name: 'Zaram' };

describe('an untouched field is not the same as a cleared one', () => {
  it('omits a field that was not passed', async () => {
    fetchMock.mockResolvedValue(json(stored));
    await saveCharacter({ assistantName: 'Ada' });

    const body = sentBody();
    expect(body).toHaveProperty('assistant_name', 'Ada');
    // The two that were not passed must be absent, not empty — an empty string
    // would clear them, wiping a manner the user set weeks ago.
    expect(body).not.toHaveProperty('manner');
    expect(body).not.toHaveProperty('voice');
  });

  it('sends an empty string when a field is deliberately cleared', async () => {
    fetchMock.mockResolvedValue(json(stored));
    await saveCharacter({ manner: '' });

    expect(sentBody()).toHaveProperty('manner', '');
  });
});

describe('what comes back is what will be used', () => {
  it('returns the stored value rather than the submitted one', async () => {
    // The backend collapses whitespace and bounds length. Echoing the input
    // would show the user a name Zaram is not going to use.
    fetchMock.mockResolvedValue(
      json({ assistant_name: 'Ada Lovelace', manner: '', voice: '', default_name: 'Zaram' }),
    );
    const result = await saveCharacter({ assistantName: '  Ada    Lovelace  ' });

    expect(result.assistantName).toBe('Ada Lovelace');
  });

  it('reads the default name from the backend rather than hardcoding it', async () => {
    fetchMock.mockResolvedValue(json({ ...stored, default_name: 'Zaram' }));
    expect((await fetchCharacter()).defaultName).toBe('Zaram');
  });

  it('falls back to the product name only when the backend sends none', async () => {
    fetchMock.mockResolvedValue(json({ assistant_name: 'Ada' }));
    const result = await fetchCharacter();
    expect(result.defaultName).toBe('Zaram');
    // Missing strings become empty, never undefined, so a form never renders
    // the literal "undefined" into an input.
    expect(result.manner).toBe('');
    expect(result.voice).toBe('');
  });
});

describe('a mutating call is preflighted', () => {
  it('carries X-Zaram-Client so a browser must ask first', async () => {
    fetchMock.mockResolvedValue(json(stored));
    await saveCharacter({ assistantName: 'Ada' });

    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>;
    expect(headers['X-Zaram-Client']).toBe('zaram-ui');
  });
});

describe('failures keep the backend sentence', () => {
  it('surfaces detail rather than a status code', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'A name is a word, not a paragraph.' }, 400));

    await expect(saveCharacter({ assistantName: 'x'.repeat(500) })).rejects.toThrow(
      'A name is a word, not a paragraph.',
    );
    await expect(saveCharacter({ assistantName: 'x' })).rejects.toBeInstanceOf(CharacterError);
  });
});

describe('an absent voice list is ordinary, not a failure', () => {
  it('returns nothing when the speech extra is not installed', async () => {
    fetchMock.mockResolvedValue(json({ voices: {} }));
    expect(await fetchVoices()).toEqual([]);
  });

  it('never throws, so a missing voice list cannot stop someone naming it', async () => {
    fetchMock.mockRejectedValue(new Error('connection refused'));
    expect(await fetchVoices()).toEqual([]);
  });

  it('accepts either the dict the backend sends or a plain list', async () => {
    fetchMock.mockResolvedValue(json({ voices: { af_heart: {}, am_adam: {} } }));
    expect(await fetchVoices()).toEqual(['af_heart', 'am_adam']);

    fetchMock.mockResolvedValue(json({ voices: ['af_heart'] }));
    expect(await fetchVoices()).toEqual(['af_heart']);
  });

  it('reads the id out of a row rather than printing "[object Object]"', async () => {
    fetchMock.mockResolvedValue(json({ voices: [{ id: 'af_heart' }, { id: 'am_adam' }] }));
    expect(await fetchVoices()).toEqual(['af_heart', 'am_adam']);
  });
});

describe('the voice catalogue', () => {
  const row = {
    id: 'bf_emma',
    name: 'Emma',
    language: 'British English',
    language_code: 'b',
    gender: 'female',
    grade: 'B-',
    size_bytes: 523000,
    installed: false,
    requires: null,
    default: false,
  };

  it('keeps the grade the author gave and does not invent one where he gave none', async () => {
    fetchMock.mockResolvedValue(
      json({ generated: '2026-10-04', voices: [row, { ...row, id: 'ef_dora', grade: null }] }),
    );
    const found = await fetchVoiceCatalogue();
    expect(found.generated).toBe('2026-10-04');
    expect(found.voices.map((v) => v.grade)).toEqual(['B-', null]);
  });

  it('never throws, so a failed list cannot stop someone naming it', async () => {
    fetchMock.mockRejectedValue(new Error('connection refused'));
    expect(await fetchVoiceCatalogue()).toEqual({ generated: null, voices: [] });
  });

  it('downloads by posting to the voice’s own route', async () => {
    fetchMock.mockResolvedValue(json({ id: 'bf_emma', installed: true }));
    await downloadVoice('bf_emma');
    expect(fetchMock.mock.calls[0][0]).toContain('/voice/voices/bf_emma/download');
    expect(fetchMock.mock.calls[0][1].method).toBe('POST');
  });

  it('surfaces the backend sentence when a download fails', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'Zaram could not fetch that voice.' }, 502));
    await expect(downloadVoice('bf_emma')).rejects.toThrow('Zaram could not fetch that voice.');
  });
});
