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

function catalogue(models: unknown[], budget: number | null = 9_000_000_000) {
  return { models, budget_bytes: budget, generated: '2026-09-24' };
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

  it('says so when the manifest could not be read', async () => {
    fetchModelCatalogue.mockResolvedValue(catalogue([]));
    await open();
    await waitFor(() =>
      expect(screen.getByTestId('no-models').textContent).toMatch(/could not read/i),
    );
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
