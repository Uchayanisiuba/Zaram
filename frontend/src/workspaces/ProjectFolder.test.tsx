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

const selectDirectory = vi.fn();

// The bridge, mocked at the seam the component actually calls. The unit tests
// at the bottom cover `chosenPath`; this covers the wiring, which is the half
// that broke — `UnfinishedTasks.test.tsx` next door explains why that
// distinction is the one that matters here.
vi.mock('@/desktop/desktop-bridge', () => ({
  isDesktop: true,
  desktop: { dialog: { selectDirectory: (...a: unknown[]) => selectDirectory(...a) } },
}));

import ProjectWorkspace, { chosenPath } from './ProjectWorkspace';

const CODING = {
  id: 'ride-hail',
  name: 'RIde_hail',
  type: 'coding',
  note: '',
  root: '',
  writes: false,
  runs: false,
  drives: false,
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

/** **The Choose button, which was dropping what you picked.**
 *
 * Reported 29 September 2026: the dialog opened, a folder was selected, and
 * nothing arrived — "the only way right now is to copy the text of the
 * directory and paste it."
 *
 * `fileDialogService.selectDirectory` unwraps Electron's reply and returns a
 * bare path; `RepositoryField` read it as Electron's raw reply,
 * `answer?.filePaths?.[0]`. A string asked for `.filePaths` gives `undefined`,
 * so the folder was dropped. Two halves each right against a different
 * assumption, with nothing exercising the join — which is why this is tested
 * at the join rather than on either side of it.
 */
describe('what the desktop hands back when a folder is chosen', () => {
  it('takes the bare path the service actually returns', () => {
    // The shape that shipped, and the one that was being dropped.
    expect(chosenPath('C:\Ride_app')).toBe('C:\Ride_app');
  });

  it('still takes Electron’s raw reply, so the service may change its mind', () => {
    expect(chosenPath({ filePaths: ['C:\Ride_app'] })).toBe('C:\Ride_app');
    expect(chosenPath({ filePath: 'C:\Ride_app' })).toBe('C:\Ride_app');
  });

  it('gives nothing for a cancelled dialog', () => {
    expect(chosenPath(null)).toBe('');
    expect(chosenPath(undefined)).toBe('');
  });

  it('never invents a path from a shape it does not understand', () => {
    // A path guessed from an unrecognised reply is the one value that must
    // never reach something which resolves every file operation against it.
    expect(chosenPath({ canceled: true })).toBe('');
    expect(chosenPath({ filePaths: [] })).toBe('');
    expect(chosenPath(42)).toBe('');
  });
});

describe('pressing Choose', () => {
  it('puts the folder the dialog returned into the field', async () => {
    // The bare string the service really returns. Before the fix this was read
    // as `answer.filePaths[0]`, gave undefined, and the field stayed empty —
    // a dialog that opened, took a choice, and did nothing with it.
    selectDirectory.mockResolvedValue('C:\Ride_app');
    server({ projects: [CODING] });
    render(<ProjectWorkspace />);

    fireEvent.click(await screen.findByTestId('repository-choose'));

    await waitFor(() =>
      expect((screen.getByTestId('repository-path') as HTMLInputElement).value).toBe(
        'C:\Ride_app',
      ),
    );
  });

  it('leaves the field alone when the dialog is cancelled', async () => {
    selectDirectory.mockResolvedValue(null);
    server({ projects: [CODING] });
    render(<ProjectWorkspace />);

    const field = (await screen.findByTestId('repository-path')) as HTMLInputElement;
    fireEvent.change(field, { target: { value: 'C:\typed' } });
    fireEvent.click(screen.getByTestId('repository-choose'));

    await waitFor(() => expect(field.value).toBe('C:\typed'));
  });

  it('does not take the New Folder button away from the dialog', async () => {
    // `properties: ['openDirectory']` used to land in an Object.assign over the
    // service default of ['openDirectory','createDirectory'] and replace it —
    // removing New Folder from the one person who needs it, somebody pointing
    // a brand-new project at a folder that does not exist yet.
    selectDirectory.mockResolvedValue('C:\Ride_app');
    server({ projects: [CODING] });
    render(<ProjectWorkspace />);
    fireEvent.click(await screen.findByTestId('repository-choose'));

    await waitFor(() => expect(selectDirectory).toHaveBeenCalled());
    expect(selectDirectory.mock.calls[0][0]).not.toHaveProperty('properties');
  });
});

/**
 * Reported 3 October 2026: Create is pressed, and nothing happens at all.
 *
 * Not a refusal — a refusal is a 400 and the screen says so. This is the
 * case where the request never completes: the backend is still starting, the
 * connection drops, the body is not JSON. `create` rejected, `setBusy(false)`
 * never ran, and the button disabled itself permanently with no message.
 *
 * The assertions are the person's experience rather than the mechanism: the
 * button must come back, and the screen must say something. A different fix
 * that delivers both still passes.
 */
describe('when the create request never completes', () => {
  function serverThatDropsThePost() {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === 'POST') throw new TypeError('Failed to fetch');
        if (String(input).includes('/plans')) {
          return new Response(JSON.stringify({ plans: [], kept_for_days: 7 }), { status: 200 });
        }
        return new Response(JSON.stringify({ projects: [], unclaimed: [] }), { status: 200 });
      }),
    );
  }

  async function fillInACodingProject() {
    const name = await openCreate();
    fireEvent.change(name, { target: { value: 'Ride hail' } });
    fireEvent.click(screen.getByRole('button', { name: /^coding$/i }));
    fireEvent.change(screen.getByTestId('repository-path'), {
      target: { value: 'C:\\Ride_app' },
    });
    return screen.getByRole('button', { name: /^create$/i }) as HTMLButtonElement;
  }

  it('leaves the button pressable instead of disabling it forever', async () => {
    serverThatDropsThePost();
    const create = await fillInACodingProject();
    expect(create.disabled).toBe(false);

    fireEvent.click(create);

    // The whole bug: `busy` never cleared, so this stayed true and no further
    // press could do anything.
    await waitFor(() => expect(create.disabled).toBe(false));
  });

  it('says something, rather than failing silently', async () => {
    serverThatDropsThePost();
    const create = await fillInACodingProject();
    fireEvent.click(create);

    // Any sentence will do; what must not happen is nothing. A button that
    // does nothing and says nothing reads as a broken product.
    await waitFor(() => {
      const said = screen.queryByText(/could not|failed|try again|not be created/i);
      expect(said).toBeTruthy();
    });
  });

  it('keeps the form open so the typing is not lost', async () => {
    serverThatDropsThePost();
    const create = await fillInACodingProject();
    fireEvent.click(create);

    await waitFor(() => expect(create.disabled).toBe(false));
    expect((screen.getByLabelText('Project name') as HTMLInputElement).value).toBe('Ride hail');
    expect((screen.getByTestId('repository-path') as HTMLInputElement).value).toBe('C:\\Ride_app');
  });
});

describe('the three grants are three boxes', () => {
  /**
   * Driving shipped on 3 October under `runs`, with the sentence beside that
   * box widened to say so. The maintainer's call the same day was that it
   * should be its own grant, and they are right: `npm test` is bounded and
   * named, while pressing whatever is on a page is not — the hazard being a
   * dev build pointed at a production database. Somebody can want the first
   * and not the second.
   *
   * So what is worth asserting is not that a third box exists. It is that
   * each box sends **its own field** and nothing else: a toggle that quietly
   * patched two grants would be the widening this split undoes, wearing a
   * checkbox.
   */
  const WITH_FOLDER = { ...CODING, root: 'E:\Keyline' };

  it('renders all three, off', async () => {
    server({ projects: [WITH_FOLDER] });
    render(<ProjectWorkspace />);
    for (const id of ['edits-allowed', 'runs-allowed', 'drives-allowed']) {
      const box = await screen.findByTestId(id);
      expect((box as HTMLInputElement).checked).toBe(false);
    }
  });

  it('each box patches only its own grant', async () => {
    const sent = server({ projects: [WITH_FOLDER] });
    render(<ProjectWorkspace />);

    for (const [id, field] of [
      ['edits-allowed', 'writes'],
      ['runs-allowed', 'runs'],
      ['drives-allowed', 'drives'],
    ] as const) {
      sent.length = 0;
      fireEvent.click(await screen.findByTestId(id));
      await waitFor(() => expect(sent.length).toBeGreaterThan(0));
      const patch = sent.find((s) => s.body && field in s.body);
      expect(patch, `${id} sent no ${field}`).toBeTruthy();
      expect(Object.keys(patch!.body)).toEqual([field]);
    }
  });

  it('says nothing about driving while the box is off', async () => {
    server({ projects: [WITH_FOLDER] });
    render(<ProjectWorkspace />);
    await screen.findByTestId('drives-allowed');
    expect(screen.queryByText(/carries none of/i)).toBeNull();
  });

  it('says what driving costs once the box is on', async () => {
    // Named rather than asked for on trust, the same way the sentence beside
    // `runs` names the runners it would run.
    server({ projects: [{ ...WITH_FOLDER, drives: true }] });
    render(<ProjectWorkspace />);
    await waitFor(() => expect(screen.getByText(/carries none of/i)).toBeTruthy());
    expect(screen.getByText(/Localhost only/i)).toBeTruthy();
  });

  it('the runs sentence no longer claims driving', async () => {
    // The widened copy, gone. It said running the commands "includes …
    // driving it in a browser", which is what the split makes untrue.
    server({ projects: [{ ...WITH_FOLDER, runs: true }] });
    render(<ProjectWorkspace />);
    await screen.findByTestId('runs-allowed');
    expect(screen.queryByText(/That includes starting the app and driving it/i)).toBeNull();
  });
});

describe('one press to build and run', () => {
  const WITH_FOLDER = { ...CODING, root: 'E:\Keyline', shell: false };

  it('sets all four grants in one request, and says what still asks', async () => {
    const sent = server({ projects: [WITH_FOLDER] });
    render(<ProjectWorkspace />);

    fireEvent.click(await screen.findByTestId('build-allowed'));

    await waitFor(() => expect(sent.some((s) => s.body && 'shell' in s.body)).toBe(true));
    const patches = sent.filter((s) => s.body && 'writes' in s.body);
    expect(patches).toHaveLength(1);
    expect(patches[0].body).toEqual({ writes: true, runs: true, drives: true, shell: true });
  });

  it('is on only when all four are, and turning it off withdraws all four', async () => {
    const sent = server({ projects: [{ ...WITH_FOLDER, writes: true, runs: true, drives: true, shell: true }] });
    render(<ProjectWorkspace />);
    const box = (await screen.findByTestId('build-allowed')) as HTMLInputElement;
    expect(box.checked).toBe(true);
    expect(screen.getByText(/still ask, one click each/)).toBeTruthy();

    fireEvent.click(box);
    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent.find((s) => s.body && 'writes' in s.body)!.body).toEqual({
      writes: false, runs: false, drives: false, shell: false,
    });
  });

  it('partly on reads as off, and pressing it turns the rest on', async () => {
    const sent = server({ projects: [{ ...WITH_FOLDER, writes: true }] });
    render(<ProjectWorkspace />);
    const box = (await screen.findByTestId('build-allowed')) as HTMLInputElement;
    expect(box.checked).toBe(false);
    fireEvent.click(box);
    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent.find((s) => s.body && 'writes' in s.body)!.body.shell).toBe(true);
  });
});

describe('a folder is enough to name a coding project — 5 October 2026', () => {
  // Reported: a folder was chosen, the form looked complete, and Create stayed
  // dim with nothing saying why. The name field above it was empty.
  async function chooseFolder(path: string) {
    const sent = server();
    await openCreate();
    fireEvent.click(screen.getByRole('button', { name: /^coding$/i }));
    fireEvent.change(screen.getByTestId('repository-path'), { target: { value: path } });
    return sent;
  }

  it('takes the folder’s name, enables Create, and says so', async () => {
    const sent = await chooseFolder('E:\\Mine_Craft_Test');
    const create = screen.getByRole('button', { name: /^create$/i }) as HTMLButtonElement;
    expect(create.disabled).toBe(false);
    expect(screen.getByTestId('create-uses-folder-name').textContent).toContain('Mine_Craft_Test');
    expect((screen.getByLabelText('Project name') as HTMLInputElement).placeholder).toBe('Mine_Craft_Test');

    fireEvent.click(create);
    await waitFor(() => {
      const post = sent.find((s) => s.body?.root === 'E:\\Mine_Craft_Test');
      expect(post?.body.name).toBe('Mine_Craft_Test');
    });
  });

  it('a name that is typed always wins', async () => {
    const sent = await chooseFolder('E:\\Mine_Craft_Test');
    fireEvent.change(screen.getByLabelText('Project name'), { target: { value: 'Block World' } });
    expect(screen.queryByTestId('create-uses-folder-name')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /^create$/i }));
    await waitFor(() => expect(sent.find((s) => s.body?.name === 'Block World')?.body.root).toBe('E:\\Mine_Craft_Test'));
  });

  it('handles a trailing slash and forward slashes', async () => {
    await chooseFolder('/home/me/block-world/');
    expect(screen.getByTestId('create-uses-folder-name').textContent).toContain('block-world');
  });

  it('a bare drive is not a name, so Create says what is missing', async () => {
    await chooseFolder('E:\\');
    expect((screen.getByRole('button', { name: /^create$/i }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByTestId('create-needs-name')).toBeTruthy();
  });

  it('says what is missing when there is neither name nor folder suggestion', async () => {
    server();
    await openCreate();
    expect(screen.getByTestId('create-needs-name').textContent).toContain('Give it a name');
  });
});
