/**
 * @vitest-environment node
 *
 * Assignment's wire format, where "nowhere" has to survive the trip.
 *
 * The backend draws a distinction the UI can erase by accident: `null` means
 * *the caller said nothing* and is refused, `""` means *take it out of its
 * project* and is honoured. Every ordinary instinct — dropping falsy fields,
 * `body.project_id || undefined`, a spread that skips empties — collapses the
 * two, and the visible result is that **Remove silently fails** while
 * everything else keeps working.
 *
 * That failure is invisible from the surface: the request goes out, an error
 * appears in a place nobody is looking, and the file simply stays where it was.
 * So the empty string is asserted here rather than left to a click-through.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { assignToProject } from './artifactsClient';
import { scopeProjectId, setMemoryScope } from './memoryClient';

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Capture the single request a client makes. */
function captureRequest(status = 200) {
  const seen: { url: string; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit) => {
      seen.push({ url, init });
      return new Response(status === 200 ? '{}' : 'nope', { status });
    }),
  );
  return seen;
}

const bodyOf = (init: RequestInit) => JSON.parse(String(init.body));

describe('moving a file', () => {
  it('sends the empty string when a file leaves its project', async () => {
    const seen = captureRequest();

    await assignToProject('art_1', '');

    expect(bodyOf(seen[0].init)).toEqual({ project_id: '' });
    // Not omitted, and not null: the backend reads both as "you said nothing"
    // and refuses, so Remove would fail while every other path worked.
    expect('project_id' in bodyOf(seen[0].init)).toBe(true);
  });

  it('patches the artifact rather than posting a new one', async () => {
    const seen = captureRequest();

    await assignToProject('art_1', 'harbour-lane');

    expect(seen[0].init.method).toBe('PATCH');
    expect(seen[0].url).toContain('/artifacts/art_1');
    expect(bodyOf(seen[0].init)).toEqual({ project_id: 'harbour-lane' });
  });

  it('reports a refusal instead of resolving quietly', async () => {
    captureRequest(400);

    // A rejected move that resolves is worse than one that throws: the row
    // re-renders unchanged and the user reads that as "it did not take".
    await expect(assignToProject('art_1', 'ghost')).rejects.toThrow();
  });
});

describe('moving a fact', () => {
  it('sends the empty string for global', async () => {
    const seen = captureRequest();

    await setMemoryScope('mem_1', '');

    expect(bodyOf(seen[0].init)).toEqual({ project_id: '' });
    expect(seen[0].url).toContain('/memory/mem_1/scope');
  });

  it('reports a refusal instead of resolving quietly', async () => {
    captureRequest(400);

    await expect(setMemoryScope('mem_1', 'ghost')).rejects.toThrow();
  });
});

describe('reading a scope', () => {
  it('finds the project in a project scope', () => {
    expect(scopeProjectId('project:harbour-lane')).toBe('harbour-lane');
  });

  it('calls global what it is, rather than a project called global', () => {
    // `global` is a scope, not a project id. Returning it as one would put a
    // badge on every fact and offer to "remove" the user's own preferences
    // from a project that does not exist.
    expect(scopeProjectId('global')).toBeNull();
    expect(scopeProjectId(undefined)).toBeNull();
    expect(scopeProjectId('')).toBeNull();
  });

  it('does not read a bare prefix as a project', () => {
    expect(scopeProjectId('project:')).toBeNull();
  });
});
