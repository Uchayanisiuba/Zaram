/**
 * The rules the first-run screen must not break.
 *
 * Every one of these is enforced on the backend and trivially undone in a
 * component — a price moved into a `title`, an absent download rendered as
 * "0 MB", a helpful example filename added to a detail line. They are asserted
 * here because the component is where they would be lost, and because the
 * screen is seen once per user and there is no second first impression.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, act } from '@testing-library/react';

import FirstRunPanel from './FirstRunPanel';
import { ENGINE_DOWNLOAD_URL, WATCH_EVERY_MS } from './EngineInstall';
import { pullRecommendedModel } from '@/services/pullClient';
import type { ReadinessReport } from '@/services/readinessClient';

// The download itself, stubbed. What is asserted here is *when* it is asked
// for — never on the click that opens the row — and that the screen re-asks
// readiness when it ends. The stream's own shapes are `ModelPull`'s tests.
vi.mock('@/services/pullClient', () => ({
  pullRecommendedModel: vi.fn(async (onEvent: (e: Record<string, unknown>) => void) => {
    onEvent({ stage: 'Downloading', completed: 1, total: 2 });
    onEvent({ done: true });
  }),
}));

// `CloudKeyForm` reads the shipped provider manifest on mount. Stubbed rather
// than left to fail, because an unstubbed fetch lands the form in its
// `unavailable` state — which is correct behaviour and would make the tests
// below assert nothing about the thing they name.
vi.mock('@/services/settingsClient', () => ({
  fetchProviderCatalogue: vi.fn(async () => ({
    generated: '2026-08-01',
    providers: [
      {
        id: 'openrouter',
        displayName: 'OpenRouter',
        baseUrl: 'https://openrouter.ai/api/v1',
        available: true,
        note: 'Free models here are logged and may be trained on.',
        keyUrl: 'https://openrouter.ai/keys',
        compatibility: 'openai',
        auth: 'bearer',
      },
    ],
  })),
  connectCloudProvider: vi.fn(async () => ({
    connections: [],
    configured: true,
    generated: '2026-08-01',
  })),
}));

afterEach(cleanup);

/** Shaped like the real `no_engine` payload, including its sizes. */
const noEngine: ReadinessReport = {
  readiness: 'no_engine',
  summary: 'Zaram has nothing to answer with yet. Everything else works — you just need a model.',
  canChat: false,
  offers: [
    {
      kind: 'install_engine',
      label: 'Set up a local model',
      detail: 'Installs the engine that runs models on your own machine.',
      downloadBytes: 1202590515,
      downloadLabel: '1.1 GB',
      recommendedOn: '2026-08-30',
    },
    {
      kind: 'use_cloud_key',
      label: 'Use a cloud model instead',
      detail: 'Paste a key from a provider you already pay for.',
      downloadBytes: null,
      downloadLabel: null,
      recommendedOn: null,
    },
    {
      kind: 'explore',
      label: 'Look around first',
      detail: 'Add a folder and explore what Zaram found.',
      downloadBytes: null,
      downloadLabel: null,
      recommendedOn: null,
    },
  ],
  stillWorks: [
    'Add documents to Knowledge — reading and indexing them needs no model',
    'Browse Memory, Work, Projects and the egress log',
  ],
};

/** The other unready state: Ollama is running, with nothing that can chat. */
const engineWithoutModel: ReadinessReport = {
  readiness: 'engine_without_model',
  summary: 'Almost there. The local engine is running but has no model that can hold a conversation yet.',
  canChat: false,
  offers: [
    {
      kind: 'pull_model',
      label: 'Download a model to start with',
      detail: 'The usual choice. Good at the five jobs a local model does well.',
      downloadBytes: 4700000000,
      downloadLabel: '4.4 GB',
      recommendedOn: '2026-08-30',
    },
    ...noEngine.offers.filter((o) => o.kind !== 'install_engine'),
  ],
  stillWorks: noEngine.stillWorks,
};

const offerButton = (kind: string) =>
  document.querySelector<HTMLButtonElement>(`[data-offer="${kind}"]`)!;

describe('the first-run screen', () => {
  it('states what is missing, in the backend’s words', () => {
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} onConnected={() => {}} />);

    expect(screen.getByText(noEngine.summary)).toBeInTheDocument();
  });

  it('puts the download size on the button, not behind a tooltip', () => {
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} onConnected={() => {}} />);

    // Read off the accessible name: a size in a `title` or a hover card is a
    // price the user has to go looking for, which is not a price stated.
    expect(offerButton('install_engine')).toHaveAccessibleName(/1\.1 GB/);
  });

  it('shows no size at all when nothing is downloaded', () => {
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} onConnected={() => {}} />);

    // Not "0 MB". Zero is a figure and it reads as free rather than as absent.
    expect(offerButton('use_cloud_key').textContent).not.toMatch(/\d+\s*(MB|GB)/);
    expect(offerButton('explore').textContent).not.toMatch(/\d+\s*(MB|GB)/);
  });

  it('says when the model advice was written', () => {
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} onConnected={() => {}} />);

    // A recommendation is only as current as the list behind it, and the list
    // ships in the bundle — so a build a year old would otherwise name a model
    // chosen a year ago with nothing on screen saying so.
    expect(offerButton('install_engine')).toHaveAccessibleName(/2026-08-30/);
  });

  it('says nothing about a date when the recommendation has none behind it', () => {
    const fallback: ReadinessReport = {
      ...noEngine,
      offers: noEngine.offers.map((o) => ({ ...o, recommendedOn: null })),
    };
    render(<FirstRunPanel report={fallback} onExplore={() => {}} onConnected={() => {}} />);

    // The manifest was missing or unreadable and the constant answered. Dating
    // that would put a figure on the screen that nothing produced.
    expect(offerButton('install_engine').textContent).not.toMatch(/dated/i);
  });

  it('never puts a model filename on the screen', () => {
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} onConnected={() => {}} />);

    // The payload carries the model's name for whatever pulls it. The target
    // user is not technical, and this screen must not read that field — a
    // helpful `(qwen2.5:7b)` beside the label is the whole rule undone.
    expect(screen.getByTestId('first-run').textContent).not.toMatch(/qwen|llama|gguf|:\d+b/i);
  });

  it('names what still works, so the screen reads as unconfigured not broken', () => {
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} onConnected={() => {}} />);

    for (const line of noEngine.stillWorks) {
      expect(screen.getByText(line)).toBeInTheDocument();
    }
  });

  it('offers the way out that it can actually honour', async () => {
    const onExplore = vi.fn();
    render(<FirstRunPanel report={noEngine} onExplore={onExplore} onConnected={() => {}} />);

    offerButton('explore').click();

    expect(onExplore).toHaveBeenCalledTimes(1);
  });

  it('lets every offer on the screen be pressed — none is greyed', () => {
    // Reported 14 October 2026 against alpha.6: "the local model download option
    // is not clickable". On a machine with no engine the first offer is
    // `install_engine`, and it was the one thing left greyed with "Zaram can't
    // set this up for you yet". A button that takes a click and does nothing is
    // the worst thing on a first-run screen, and a greyed one reads as the same
    // thing: the user concludes the product is broken rather than unconfigured.
    //
    // So the rule is stated over every offer in both states rather than over
    // the one that happens to be greyed today: if a fifth kind is ever added
    // without an executor, this is where it is caught.
    for (const report of [noEngine, engineWithoutModel]) {
      const { unmount } = render(
        <FirstRunPanel report={report} onExplore={() => {}} onConnected={() => {}} />,
      );
      for (const offer of report.offers) {
        const button = offerButton(offer.kind);
        expect(button, offer.kind).not.toBeDisabled();
        expect(button.textContent, offer.kind).not.toMatch(/can’t set this up for you yet/);
      }
      unmount();
    }
  });

  it('opens the engine’s download page on the second press, and says what happens next', async () => {
    const opened = vi.spyOn(window, 'open').mockImplementation(() => null);
    const onConnected = vi.fn();
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} onConnected={onConnected} />);

    // Opening the row shows what will happen and opens nothing: the page is the
    // person's browser's request, and it should not begin on a curious click.
    offerButton('install_engine').click();
    await screen.findByTestId('engine-install');
    expect(opened).not.toHaveBeenCalled();
    expect(screen.getByTestId('engine-install').textContent).toMatch(/moves on by itself/i);
    expect(screen.getByTestId('engine-install').textContent).toMatch(/nothing you type leaves/i);

    screen.getByTestId('open-engine-download').click();
    expect(opened).toHaveBeenCalledWith(ENGINE_DOWNLOAD_URL, '_blank', 'noopener,noreferrer');
    await screen.findByRole('status');
    opened.mockRestore();
  });

  it('keeps asking whether the engine has started once the page is open, and stops when left', () => {
    vi.useFakeTimers();
    const opened = vi.spyOn(window, 'open').mockImplementation(() => null);
    const onConnected = vi.fn();
    const { unmount } = render(
      <FirstRunPanel report={noEngine} onExplore={() => {}} onConnected={onConnected} />,
    );
    act(() => offerButton('install_engine').click());
    // Nothing is polled before the page has been opened.
    act(() => { vi.advanceTimersByTime(WATCH_EVERY_MS * 3); });
    expect(onConnected).not.toHaveBeenCalled();

    act(() => screen.getByTestId('open-engine-download').click());
    act(() => { vi.advanceTimersByTime(WATCH_EVERY_MS * 2); });
    expect(onConnected).toHaveBeenCalledTimes(2);

    unmount();
    act(() => { vi.advanceTimersByTime(WATCH_EVERY_MS * 3); });
    expect(onConnected).toHaveBeenCalledTimes(2);
    opened.mockRestore();
    vi.useRealTimers();
  });

  it('offers a manual check once the page has been opened', () => {
    const opened = vi.spyOn(window, 'open').mockImplementation(() => null);
    const onConnected = vi.fn();
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} onConnected={onConnected} />);
    act(() => offerButton('install_engine').click());
    expect(screen.queryByTestId('check-engine')).toBeNull();
    act(() => screen.getByTestId('open-engine-download').click());
    act(() => screen.getByTestId('check-engine').click());
    expect(onConnected).toHaveBeenCalledTimes(1);
    opened.mockRestore();
  });

  it('lets the model offer be carried out, and does not start the download on a curious click', async () => {
    // Opening the row and starting a multi-gigabyte fetch are two different
    // decisions. The size is on the button, and the second press is the
    // confirmation — a download that begins on the first click is the one
    // thing a metered connection cannot forgive.
    render(<FirstRunPanel report={engineWithoutModel} onExplore={() => {}} onConnected={() => {}} />);

    expect(offerButton('pull_model')).not.toBeDisabled();

    offerButton('pull_model').click();

    expect(await screen.findByTestId('model-pull')).toBeInTheDocument();
    expect(pullRecommendedModel).not.toHaveBeenCalled();
  });

  it('asks readiness again once the model is downloaded', async () => {
    // Otherwise the setup screen stands over a product that has just become
    // able to answer, and there is nothing to dismiss it.
    const onConnected = vi.fn();
    render(
      <FirstRunPanel report={engineWithoutModel} onExplore={() => {}} onConnected={onConnected} />,
    );

    offerButton('pull_model').click();
    (await screen.findByText('Start the download')).click();

    await waitFor(() => expect(onConnected).toHaveBeenCalledTimes(1));
    expect(pullRecommendedModel).toHaveBeenCalledTimes(1);
  });

  it('lets the cloud-key offer be carried out, and opens its form in place', async () => {
    // The offer this screen can now honour. It was greyed for as long as
    // nothing could store a key; `POST /providers/cloud` writes the
    // configuration and takes effect without a restart, so the button is real.
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} onConnected={() => {}} />);

    expect(offerButton('use_cloud_key')).not.toBeDisabled();

    offerButton('use_cloud_key').click();

    // In place, under the offer it belongs to — the price and the detail above
    // it stay readable, which is the context that made the choice make sense.
    expect(await screen.findByTestId('cloud-key-form')).toBeInTheDocument();
  });

  it('does not send the user somewhere else when they choose the key offer', () => {
    // `onExplore` closes the conversation. Wiring the key offer to it would
    // dismiss the setup screen and set nothing up.
    const onExplore = vi.fn();
    render(<FirstRunPanel report={noEngine} onExplore={onExplore} onConnected={() => {}} />);

    offerButton('use_cloud_key').click();

    expect(onExplore).not.toHaveBeenCalled();
  });

  it('composes no model filenames of its own', () => {
    // The payload is asserted clean on the backend side. This asserts the
    // component adds nothing — an "e.g. …" in a detail line would be the
    // obvious, helpful-looking way to reintroduce them.
    const { container } = render(<FirstRunPanel report={noEngine} onExplore={() => {}} onConnected={() => {}} />);

    expect(container.textContent).not.toMatch(/gguf|safetensors|\bq4[_-]|:\d+b\b/i);
  });

  it('renders every offer the payload carries, including kinds it does not know', () => {
    const future: ReadinessReport = {
      ...noEngine,
      offers: [
        ...noEngine.offers,
        {
          kind: 'something_later',
          label: 'An offer this build has never heard of',
          detail: 'Written for a person, so it reads without the enum.',
          downloadBytes: null,
          downloadLabel: null,
          recommendedOn: null,
        },
      ],
    };
    render(<FirstRunPanel report={future} onExplore={() => {}} onConnected={() => {}} />);

    expect(screen.getByText('An offer this build has never heard of')).toBeInTheDocument();
    expect(offerButton('something_later')).toBeDisabled();
  });
});

describe('choosing a different model', () => {
  /** The single offer is the first-run path and stays first — `CLAUDE.md`
   *  says start with the smallest capable model and never block on a
   *  download, and a catalogue in front of somebody who has not sent a
   *  message yet is a decision they have no basis to make.
   *
   *  But one offer with no alternative reads as a product that has decided
   *  for you. One press away, never in the way. */
  it('offers the catalogue behind the suggestion', async () => {
    render(<FirstRunPanel report={engineWithoutModel} onExplore={() => {}} onConnected={() => {}} />);
    offerButton('pull_model').click();
    expect(await screen.findByTestId('toggle-model-browser')).toBeInTheDocument();
  });

  it('shows the single offer first, not the list', async () => {
    render(<FirstRunPanel report={engineWithoutModel} onExplore={() => {}} onConnected={() => {}} />);
    offerButton('pull_model').click();
    expect(await screen.findByTestId('model-pull')).toBeInTheDocument();
    expect(screen.queryByTestId('model-browser')).toBeNull();
  });

  it('and the row still has to be opened before anything downloads', () => {
    // A gigabyte-scale fetch beginning on a curious click is the one thing
    // a metered connection cannot forgive.
    render(<FirstRunPanel report={engineWithoutModel} onExplore={() => {}} onConnected={() => {}} />);
    expect(screen.queryByTestId('toggle-model-browser')).toBeNull();
  });
});
