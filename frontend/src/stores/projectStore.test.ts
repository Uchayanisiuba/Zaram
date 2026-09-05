/**
 * Adopting a group that exists only on its contents.
 *
 * The property worth a test is narrow and load-bearing: **the id passed to the
 * adopt route is the group's id, never anything derived from the name the user
 * typed.** Every artifact row and every `project:<id>` scope points at that
 * exact string, so re-slugging here would create a different project and adopt
 * nothing — while returning 200 and looking like it worked.
 *
 * The second is that the unclaimed list is a repair offer and not load-bearing
 * for the screen: a backend that cannot serve it must leave Project working.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useProjectStore } from './projectStore';

const PROJECTS = { projects: [{ id: 'harbour', name: 'Harbour Lane' }] };

function jsonOk(body: unknown) {
  return { ok: true, status: 200, json: async () => body } as Response;
}

beforeEach(() => {
  useProjectStore.setState({ projects: [], unclaimed: [], loading: false, error: null });
  vi.restoreAllMocks();
});

describe('loading', () => {
  it('reads the unclaimed groups alongside the projects', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url.includes('/unclaimed')
          ? jsonOk({ unclaimed: [{ id: 'harbour', artifacts: 2, facts: -1 }] })
          : jsonOk({ projects: [] }),
      ),
    );

    await useProjectStore.getState().load();

    expect(useProjectStore.getState().unclaimed).toEqual([
      { id: 'harbour', artifacts: 2, facts: -1 },
    ]);
  });

  it('keeps the projects screen working when the unclaimed route fails', async () => {
    // A backend too old to serve it, or a failure reading it, must not take the
    // screen down. An error banner over a working list would be Zaram
    // reporting its own new endpoint as the user's problem.
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/unclaimed')) throw new Error('no such route');
        return jsonOk(PROJECTS);
      }),
    );

    await useProjectStore.getState().load();

    expect(useProjectStore.getState().projects).toHaveLength(1);
    expect(useProjectStore.getState().unclaimed).toEqual([]);
    expect(useProjectStore.getState().error).toBeNull();
  });
});

describe('adopting', () => {
  it('sends the group id in the path, not the name', async () => {
    // The whole point. A name of "Harbour Lane" must not become `harbour-lane`
    // — the files point at `harbour`, and a project under any other id adopts
    // nothing while reporting success.
    const fetchMock = vi.fn(async (url: string, _init?: RequestInit) =>
      url.includes('/unclaimed') ? jsonOk({ unclaimed: [] }) : jsonOk(PROJECTS),
    );
    vi.stubGlobal('fetch', fetchMock);

    await useProjectStore.getState().adopt('harbour', 'Harbour Lane', 'business');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/projects/harbour/adopt');
    expect(url).not.toContain('harbour-lane');
    expect(JSON.parse(init?.body as string)).toEqual({
      name: 'Harbour Lane',
      type: 'business',
    });
  });

  it('reloads so the group leaves the unclaimed list', async () => {
    const fetchMock = vi.fn(async (url: string) =>
      url.includes('/unclaimed') ? jsonOk({ unclaimed: [] }) : jsonOk(PROJECTS),
    );
    vi.stubGlobal('fetch', fetchMock);

    await useProjectStore.getState().adopt('harbour', 'Harbour Lane', 'general');

    expect(useProjectStore.getState().unclaimed).toEqual([]);
    expect(useProjectStore.getState().projects).toHaveLength(1);
  });

  it('surfaces the backend’s reason rather than a generic failure', async () => {
    // The 409 and 404 this route returns are written for a person — "already a
    // project", "nothing to adopt". Replacing them with a house message would
    // throw away the only part that tells the user what to do next.
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 409,
        json: async () => ({ detail: "'harbour' is already a project." }),
      })),
    );

    await useProjectStore.getState().adopt('harbour', 'Harbour Lane', 'general');

    expect(useProjectStore.getState().error).toBe("'harbour' is already a project.");
  });
});
