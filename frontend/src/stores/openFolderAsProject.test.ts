/**
 * @vitest-environment jsdom
 *
 * Opening a folder as a coding project grants the edits, and nothing else.
 *
 * Reported 29 September 2026, against two coding projects that could not touch
 * a file: `writes=0`, `runs=0`, and every tool call refusing. Rule 7j is what
 * decides this — *"consent given deliberately for a destination is consent"*,
 * and *"requiring a second, separate rule afterwards asks the same question
 * twice and reads as the product being broken"*. Which is exactly how it read.
 *
 * **Why this press qualifies and creating a project in the UI does not.** The
 * person wrote a message naming this folder and asking for work on the code,
 * then pressed a button whose whole text is about opening that folder as a
 * coding project. Destination and intent in one act. Somebody typing a path
 * into Project has only said "read here".
 *
 * **And why `runs` is not granted with it.** Running a project's commands is
 * arbitrary execution, and the risk tiers ask a mutative tool for undo: a git
 * commit undoes an edit, and nothing undoes a command.
 *
 * Asserted against the store rather than the component because the store is
 * where the grant is recorded and where a later refactor would drop it.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useProjectStore } from '@/stores/projectStore';

const CREATED = {
  id: 'ride-share',
  name: 'Ride Share',
  type: 'coding',
  note: '',
  root: 'C:\\Ride Share',
  writes: false,
  runs: false,
  facts: 0,
  artifacts: 0,
};

function server() {
  const sent: { url: string; method?: string; body: any }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      sent.push({
        url,
        method: init?.method,
        body: init?.body ? JSON.parse(String(init.body)) : undefined,
      });
      if (init?.method === 'POST') {
        return new Response(JSON.stringify(CREATED), { status: 200 });
      }
      if (init?.method === 'PATCH') {
        return new Response(JSON.stringify({ ...CREATED, writes: true }), { status: 200 });
      }
      return new Response(JSON.stringify({ projects: [CREATED], unclaimed: [] }), { status: 200 });
    }),
  );
  return sent;
}

/** What `ChatSurface.openFolderAsProject` does with the store, in order. */
async function openFolderAsProject(path: string, name: string) {
  const project = await useProjectStore.getState().create(name, 'coding', '', path);
  if (!project) return null;
  await useProjectStore.getState().setWrites(project.id, true);
  return project;
}

beforeEach(() => {
  useProjectStore.setState({ error: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('opening a folder as a coding project', () => {
  it('creates it on the folder the person named', async () => {
    const sent = server();
    await openFolderAsProject('C:\\Ride Share', 'Ride Share');

    const post = sent.find((s) => s.method === 'POST');
    expect(post?.body.root).toBe('C:\\Ride Share');
    expect(post?.body.type).toBe('coding');
  });

  it('grants the edits, because the press is the grant', async () => {
    const sent = server();
    await openFolderAsProject('C:\\Ride Share', 'Ride Share');

    const patch = sent.find((s) => s.method === 'PATCH');
    expect(patch?.body).toEqual({ writes: true });
    expect(patch?.url).toContain('ride-share');
  });

  it('never grants the commands with it', async () => {
    // Nothing undoes a command. That tick stays deliberate and separate.
    const sent = server();
    await openFolderAsProject('C:\\Ride Share', 'Ride Share');

    expect(sent.every((s) => s.body?.runs === undefined)).toBe(true);
  });

  it('grants nothing when the project could not be created', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_i: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === 'POST') {
          return new Response(JSON.stringify({ detail: 'no' }), { status: 400 });
        }
        return new Response(JSON.stringify({ projects: [], unclaimed: [] }), { status: 200 });
      }),
    );

    expect(await openFolderAsProject('C:\\nope', 'nope')).toBeNull();
  });
});
