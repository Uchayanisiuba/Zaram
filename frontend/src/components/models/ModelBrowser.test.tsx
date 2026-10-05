/**
 * @vitest-environment jsdom
 *
 * Choosing a model to download.
 *
 * The classes here are the three decisions the screen makes, and each has
 * a reason that is easy to lose by making it friendlier:
 *
 * * **A model too large is greyed, never hidden** — the pack catalogue's
 *   argument, and *"disabled capabilities are visible, not silent"*.
 * * **An unmeasured machine grades nothing** — `fits === null` is a third
 *   answer, not a false. Greying the catalogue out on a Mac is wrong, and
 *   so is promising a fit nobody measured.
 * * **A failed download leaves the button** — dying at 80% on a metered
 *   connection is the worst moment to be vague.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const fetchModelCatalogue = vi.fn();
const pullRecommendedModel = vi.fn();

vi.mock('@/services/modelCatalogueClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/modelCatalogueClient')>()),
  fetchModelCatalogue: () => fetchModelCatalogue(),
}));

vi.mock('@/services/pullClient', () => ({
  pullRecommendedModel: (...a: unknown[]) => pullRecommendedModel(...(a as [])),
}));

import ModelBrowser from './ModelBrowser';

function model(over: Partial<Record<string, unknown>> = {}) {
  return {
    name: 'qwen3:8b',
    size_bytes: 5_200_000_000,
    why: 'The usual choice on a modest card.',
    generated: '2026-09-24',
    fits: true,
    recommended: true,
    installed: false,
    ...over,
  };
}

function catalogue(
  models: unknown[],
  budget: number | null = 9_000_000_000,
  outcome: 'ok' | 'unreachable' = 'ok',
) {
  return { models, budget_bytes: budget, generated: '2026-09-24', outcome };
}

beforeEach(() => {
  fetchModelCatalogue.mockReset().mockResolvedValue(catalogue([model()]));
  pullRecommendedModel.mockReset().mockResolvedValue(undefined);
});

afterEach(() => cleanup());

const user = () => userEvent.setup();

async function open() {
  render(<ModelBrowser />);
  await waitFor(() => expect(fetchModelCatalogue).toHaveBeenCalled());
}

describe('the list', () => {
  it('leads with why you would want it, not the filename', async () => {
    // The target user is not technical. The name is the quiet line.
    await open();
    await waitFor(() =>
      expect(screen.getByText('The usual choice on a modest card.')).toBeTruthy(),
    );
  });

  it('still shows the name and size, because that is what you type elsewhere', async () => {
    await open();
    await waitFor(() => expect(screen.getByText(/qwen3:8b · 5\.2 GB/)).toBeTruthy());
  });

  it('marks what the manifest suggests for this machine', async () => {
    await open();
    await waitFor(() => expect(screen.getByTestId('suggested-qwen3:8b')).toBeTruthy());
  });

  it('marks what is already here, and offers no download for it', async () => {
    fetchModelCatalogue.mockResolvedValue(catalogue([model({ installed: true })]));
    await open();
    await waitFor(() => expect(screen.getByTestId('installed-qwen3:8b')).toBeTruthy());
    expect(screen.queryByTestId('download-qwen3:8b')).toBeNull();
  });

  it('searches the sentence as well as the name', async () => {
    // What somebody remembers is "the one that reads pictures", not a tag.
    fetchModelCatalogue.mockResolvedValue(
      catalogue([
        model({ name: 'a:1b', why: 'Reads pictures as well as text.' }),
        model({ name: 'b:2b', why: 'Writes and edits.' }),
      ]),
    );
    await open();
    await user().type(screen.getByTestId('model-search'), 'pictures');
    await waitFor(() => expect(screen.queryByTestId('model-b:2b')).toBeNull());
    expect(screen.getByTestId('model-a:1b')).toBeTruthy();
  });

  it('tells "nothing matched" apart from "no list"', async () => {
    await open();
    await user().type(screen.getByTestId('model-search'), 'zzzz');
    await waitFor(() => expect(screen.getByTestId('no-models').textContent).toMatch(/Nothing matches/));
  });

  it('says the backend was unreachable when it was', async () => {
    fetchModelCatalogue.mockResolvedValue(catalogue([], null, 'unreachable'));
    await open();
    await waitFor(() =>
      expect(screen.getByTestId('no-models').textContent).toMatch(/could not reach/i),
    );
  });

  it('does not blame the backend for a list that is simply empty', async () => {
    /** **The two were one message, and a session was spent on the wrong
     *  one.** `fetchModelCatalogue` cannot throw and returns the same
     *  empty catalogue whether the request failed or came back holding
     *  nothing, so *"Zaram could not read its model list"* was printed
     *  for both — and a screenshot of it was taken as evidence of a
     *  failure that had not happened. Four causes were eliminated before
     *  the route was called over HTTP and answered 200 with seven
     *  models.
     *
     *  A diagnostic that names a cause it has not established is worse
     *  than one that says nothing. */
    fetchModelCatalogue.mockResolvedValue(catalogue([], 9_000_000_000, 'ok'));
    await open();
    await waitFor(() => expect(screen.getByTestId('no-models')).toBeTruthy());
    expect(screen.getByTestId('no-models').textContent).not.toMatch(/could not reach/i);
    expect(screen.getByTestId('no-models').textContent).toMatch(/nothing to offer/i);
  });
});

describe('a model this machine cannot run', () => {
  it('is listed, not hidden', async () => {
    // A list that silently omits the 27B leaves somebody wondering whether
    // Zaram knows it exists.
    fetchModelCatalogue.mockResolvedValue(
      catalogue([model({ name: 'big:27b', fits: false, recommended: false })]),
    );
    await open();
    await waitFor(() => expect(screen.getByTestId('model-big:27b')).toBeTruthy());
  });

  it('says why, and offers no button', async () => {
    // Offering one that cannot work is the shape of a product that looks
    // broken.
    fetchModelCatalogue.mockResolvedValue(
      catalogue([model({ name: 'big:27b', fits: false, recommended: false })]),
    );
    await open();
    await waitFor(() => expect(screen.getByTestId('too-large-big:27b')).toBeTruthy());
    expect(screen.queryByTestId('download-big:27b')).toBeNull();
  });
});

describe('a machine Zaram could not measure', () => {
  /** Apple and DirectML report no VRAM. `fits === null` is a third answer
   *  and must render as neither of the other two. */
  it('grades nothing as too large', async () => {
    fetchModelCatalogue.mockResolvedValue(
      catalogue([model({ name: 'big:27b', fits: null, recommended: false })], null),
    );
    await open();
    await waitFor(() => expect(screen.getByTestId('model-big:27b')).toBeTruthy());
    expect(screen.queryByTestId('too-large-big:27b')).toBeNull();
  });

  it('still offers the download rather than withholding it', async () => {
    fetchModelCatalogue.mockResolvedValue(
      catalogue([model({ fits: null })], null),
    );
    await open();
    await waitFor(() => expect(screen.getByTestId('download-qwen3:8b')).toBeTruthy());
  });

  it('says it could not measure, rather than reporting no room', async () => {
    fetchModelCatalogue.mockResolvedValue(catalogue([model({ fits: null })], null));
    await open();
    await waitFor(() => expect(screen.getByText(/could not measure/i)).toBeTruthy());
  });
});

describe('downloading', () => {
  it('sends the name of the row that was pressed', async () => {
    // The browser's whole point. The backend validates it against the
    // manifest, so the name selects rather than describes.
    await open();
    await user().click(screen.getByTestId('download-qwen3:8b'));
    await waitFor(() => expect(pullRecommendedModel).toHaveBeenCalled());
    expect(pullRecommendedModel.mock.calls[0][2]).toBe('qwen3:8b');
  });

  it('counts progress against the pull, never the quoted size', async () => {
    // The manifest's figure is approximate and dated. Counting against it
    // produces a bar that reaches 103% or stalls at 96%.
    pullRecommendedModel.mockImplementation(async (onEvent: (e: unknown) => void) => {
      onEvent({ stage: 'Downloading', completed: 1_000_000_000, total: 4_000_000_000 });
    });
    await open();
    await user().click(screen.getByTestId('download-qwen3:8b'));
    await waitFor(() => expect(screen.getByTestId('pull-progress')).toBeTruthy());
    expect((screen.getByTestId('pull-progress') as HTMLElement).style.width).toBe('25%');
  });

  it('reloads the list when it finishes, so the row becomes installed', async () => {
    pullRecommendedModel.mockImplementation(async (onEvent: (e: unknown) => void) => {
      onEvent({ done: true });
    });
    await open();
    fetchModelCatalogue.mockClear();
    await user().click(screen.getByTestId('download-qwen3:8b'));
    await waitFor(() => expect(fetchModelCatalogue).toHaveBeenCalled());
  });

  it('a failure says what happened and leaves the button', async () => {
    pullRecommendedModel.mockImplementation(async (onEvent: (e: unknown) => void) => {
      onEvent({ error: 'the connection dropped' });
    });
    await open();
    await user().click(screen.getByTestId('download-qwen3:8b'));
    await waitFor(() =>
      expect(screen.getByTestId('model-browser-error').textContent).toMatch(/connection dropped/),
    );
    expect(screen.getByTestId('download-qwen3:8b')).toBeTruthy();
  });

  it('only one download at a time', async () => {
    pullRecommendedModel.mockImplementation(
      () => new Promise(() => {}),
    );
    fetchModelCatalogue.mockResolvedValue(
      catalogue([model({ name: 'a:1b' }), model({ name: 'b:2b' })]),
    );
    await open();
    await user().click(screen.getByTestId('download-a:1b'));
    await waitFor(() =>
      expect((screen.getByTestId('download-b:2b') as HTMLButtonElement).disabled).toBe(true),
    );
  });
});

describe('the list says how old it is', () => {
  it('shows the manifest date', async () => {
    // Required to be visible: a recommendation is only as current as the
    // list it came from.
    await open();
    await waitFor(() => expect(screen.getByText(/List from 2026-09-24/)).toBeTruthy());
  });

  it('and what the grading was measured against', async () => {
    await open();
    await waitFor(() => expect(screen.getByText(/9\.0 GB beside the parts/)).toBeTruthy());
  });
});

describe('what a model can do, and the details behind a row', () => {
  it('draws a badge for each capability the list states', async () => {
    fetchModelCatalogue.mockResolvedValue(
      catalogue([model({ capabilities: ['vision', 'tools'] })]),
    );
    await open();
    expect(await screen.findByTestId('capability-qwen3:8b-vision')).toHaveTextContent('reads images');
    expect(screen.getByTestId('capability-qwen3:8b-tools')).toBeInTheDocument();
    expect(screen.queryByTestId('capability-qwen3:8b-thinking')).toBeNull();
  });

  it('draws nothing for a model the list says nothing about', async () => {
    await open();
    await screen.findByTestId('model-qwen3:8b');
    expect(screen.queryByLabelText('What it can do')).toBeNull();
  });

  it('says "does not say" in the details, never "cannot"', async () => {
    await open();
    await user().click(await screen.findByTestId('details-qwen3:8b'));
    const panel = screen.getByTestId('details-panel-qwen3:8b');
    expect(panel).toHaveTextContent('does not say');
    expect(panel).not.toHaveTextContent(/cannot (see|use|think)/i);
  });

  it('does not claim a fit nobody measured', async () => {
    fetchModelCatalogue.mockResolvedValue(catalogue([model({ fits: null })], null));
    await open();
    await user().click(await screen.findByTestId('details-qwen3:8b'));
    expect(screen.getByTestId('details-panel-qwen3:8b')).toHaveTextContent('could not measure');
  });

  it('opens one panel at a time and closes it again', async () => {
    fetchModelCatalogue.mockResolvedValue(
      catalogue([model(), model({ name: 'qwen3:4b' })]),
    );
    await open();
    const u = user();
    await u.click(await screen.findByTestId('details-qwen3:8b'));
    await u.click(screen.getByTestId('details-qwen3:4b'));
    expect(screen.queryByTestId('details-panel-qwen3:8b')).toBeNull();
    expect(screen.getByTestId('details-panel-qwen3:4b')).toBeInTheDocument();
    await u.click(screen.getByTestId('details-qwen3:4b'));
    expect(screen.queryByTestId('details-panel-qwen3:4b')).toBeNull();
  });
});

describe('a TabbyAPI build', () => {
  const tabby = (over: Partial<Record<string, unknown>> = {}) =>
    model({
      name: 'Qwen3.8-27B-exl3-2.20bpw',
      size_bytes: 7_425_000_000,
      runtime: 'tabby',
      recommended: false,
      install_command:
        'hf download turboderp/Qwen3.8-27B-exl3 --revision SC_2.20bpw_H3_V3 --local-dir "<your TabbyAPI models folder>/Qwen3.8-27B-exl3-2.20bpw"',
      ...over,
    });

  it('has no download button, because Zaram cannot fetch it', async () => {
    fetchModelCatalogue.mockResolvedValue(catalogue([tabby()]));
    await open();
    await screen.findByTestId('model-Qwen3.8-27B-exl3-2.20bpw');
    expect(screen.queryByTestId('download-Qwen3.8-27B-exl3-2.20bpw')).toBeNull();
    expect(screen.getByTestId('via-tabby-Qwen3.8-27B-exl3-2.20bpw')).toHaveTextContent('you fetch this one');
  });

  it('says in the row that TabbyAPI serves it', async () => {
    fetchModelCatalogue.mockResolvedValue(catalogue([tabby()]));
    await open();
    expect(await screen.findByTestId('model-Qwen3.8-27B-exl3-2.20bpw')).toHaveTextContent('TabbyAPI');
  });

  it('gives the command in Details, with the folder left as a placeholder', async () => {
    fetchModelCatalogue.mockResolvedValue(catalogue([tabby()]));
    await open();
    await user().click(await screen.findByTestId('details-Qwen3.8-27B-exl3-2.20bpw'));
    const command = screen.getByTestId('command-Qwen3.8-27B-exl3-2.20bpw');
    expect(command).toHaveTextContent('hf download turboderp/Qwen3.8-27B-exl3');
    expect(command).toHaveTextContent('<your TabbyAPI models folder>');
  });

  it('shows an installed one as installed, with no instruction to fetch it', async () => {
    fetchModelCatalogue.mockResolvedValue(catalogue([tabby({ installed: true })]));
    await open();
    expect(await screen.findByTestId('installed-Qwen3.8-27B-exl3-2.20bpw')).toBeInTheDocument();
    expect(screen.queryByTestId('via-tabby-Qwen3.8-27B-exl3-2.20bpw')).toBeNull();
  });

  it('is greyed with the reason when it will not fit, like any other', async () => {
    fetchModelCatalogue.mockResolvedValue(catalogue([tabby({ fits: false })]));
    await open();
    expect(await screen.findByTestId('too-large-Qwen3.8-27B-exl3-2.20bpw')).toBeInTheDocument();
  });

  it('leaves an ordinary Ollama row alone', async () => {
    await open();
    expect(await screen.findByTestId('download-qwen3:8b')).toBeInTheDocument();
    expect(screen.queryByTestId('via-tabby-qwen3:8b')).toBeNull();
  });

  it('copies the command', async () => {
    fetchModelCatalogue.mockResolvedValue(catalogue([tabby()]));
    // After `user()`: `userEvent.setup()` installs its own clipboard stub, and a
    // spy placed before it is replaced and never called.
    const u = user();
    const writeText = vi.spyOn(navigator.clipboard, 'writeText');
    await open();
    await u.click(await screen.findByTestId('details-Qwen3.8-27B-exl3-2.20bpw'));
    await u.click(screen.getByTestId('copy-Qwen3.8-27B-exl3-2.20bpw'));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(expect.stringContaining('hf download')));
  });
});
