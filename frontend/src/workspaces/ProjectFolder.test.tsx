/**
 * @vitest-environment jsdom
 *
 * A coding project cannot be created without a folder, and a refused one says so.
 *
 * Reported 29 September 2026: *"Zaram is not seeing my two new test coding
 * projects."* The database said what had happened —
 *
 *     ride-hail   type=coding  root=''  writes=0  runs=0
 *     ride-share  type=coding  root=''  writes=0  runs=0
 *
 * — creation had worked and everything after it had not. A coding project with
 * no root is, in `RepositoryRow`'s own words, *"an unfinished setup in which
 * every tool call refuses"*, so the person asked a question of a project that
 * could not answer it and concluded Zaram could not read their code. Exactly
 * the reading that comment was written to prevent.
 *
 * Driving `ProjectWorkspace` rather than a lifted `CreateRow`, for the reason
 * `UnfinishedTasks.test.tsx` gives next door: the wiring is the claim, and a
 * component that renders and calls nothing is how a button does nothing for a
 * fortnight while its unit tests pass.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ProjectWorkspace from './ProjectWorkspace';

const CODING = {
  id: 'ride-hail',
  name: 'RIde_hail',
  type: 'coding',
  note: '',
  root: '',
  writes: false,
  runs: false,
  facts: 0,
  artifacts: 0,
};

/** Answers every load, and records what was POSTed or PATCHed. */
function server(options: { patchFails?: string; projects?: unknown[] } = {}) {
  const sent: { url: string; body: any }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.body) sent.push({ url, body: JSON.parse(String(init.body)) });

      if (init?.method === 'PATCH' && options.patchFails) {
        return new Response(JSON.stringify({ detail: options.patchFails }), { status: 400 });
      }
      if (url.includes('/plans')) {
        return new Response(JSON.stringify({ plans: [], kept_for_days: 7 }), { status: 200 });
      }
      return new Response(
        JSON.stringify({ projects: options.projects ?? [], unclaimed: [] }),
        { status: 200 },
      );
    }),
  );
  return sent;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function openCreate() {
  render(<ProjectWorkspace />);
  const add = await screen.findByRole('button', { name: /new project|add project|create/i });
  fireEvent.click(add);
  return await screen.findByLabelText('Project name');
}

describe('creating a coding project', () => {
  it('will not create one without a folder', async () => {
    server();
    const name = await openCreate();
    fireEvent.change(name, { target: { value: 'Ride hail' } });
    fireEvent.click(screen.getByRole('button', { name: /^coding$/i }));

    const create = screen.getByRole('button', { name: /^create$/i });
    expect((create as HTMLButtonElement).disabled).toBe(true);
    // Said before the button is pressed, not discovered after.
    expect(screen.getByText(/needs its folder/i)).toBeTruthy();
  });

  it('creates it once a folder is given, and sends the folder', async () => {
    const sent = server();
    const name = await openCreate();
    fireEvent.change(name, { target: { value: 'Ride hail' } });
    fireEvent.click(screen.getByRole('button', { name: /^coding$/i }));
    fireEvent.change(screen.getByTestId('repository-path'), {
      target: { value: 'C:\\Ride_app' },
    });

    const create = screen.getByRole('button', { name: /^create$/i });
    expect((create as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(create);

    await waitFor(() => {
      const post = sent.find((s) => s.body?.name === 'Ride hail');
      expect(post?.body.root).toBe('C:\\Ride_app');
      expect(post?.body.type).toBe('coding');
    });
  });

  it('never asks a non-coding project for one', async () => {
    server();
    const name = await openCreate();
    fireEvent.change(name, { target: { value: 'Household' } });
    // `general` is the default, so nothing has been pressed.
    expect(screen.queryByTestId('repository-path')).toBeNull();
    expect((screen.getByRole('button', { name: /^create$/i }) as HTMLButtonElement).disabled).toBe(
      false,
    );
  });
});

describe('pointing an existing project at a folder', () => {
  it('shows the refusal on the row, not only at the top of the page', async () => {
    // The report was "I can't seem to connect a project to a folder". `setRoot`
    // already carried the backend's own sentence; the workspace rendered it
    // several hundred pixels above the row, so a typo looked like a dead button.
    server({
      patchFails: 'C:\\Ride_ap is not a folder on this machine.',
      projects: [CODING],
    });
    render(<ProjectWorkspace />);

    const field = await screen.findByTestId('repository-path');
    fireEvent.change(field, { target: { value: 'C:\\Ride_ap' } });
    fireEvent.click(screen.getByTestId('repository-save'));

    const refused = await screen.findByTestId('repository-refused');
    expect(refused.textContent).toContain('not a folder on this machine');
  });

  it('says plainly that a folderless coding project can do nothing', async () => {
    server({ projects: [CODING] });
    render(<ProjectWorkspace />);
    expect(await screen.findByText(/No repository yet/i)).toBeTruthy();
  });
});
