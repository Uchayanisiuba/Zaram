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
import { render, screen, cleanup } from '@testing-library/react';

import FirstRunPanel from './FirstRunPanel';
import type { ReadinessReport } from '@/services/readinessClient';

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
    },
    {
      kind: 'use_cloud_key',
      label: 'Use a cloud model instead',
      detail: 'Paste a key from a provider you already pay for.',
      downloadBytes: null,
      downloadLabel: null,
    },
    {
      kind: 'explore',
      label: 'Look around first',
      detail: 'Add a folder and explore what Zaram found.',
      downloadBytes: null,
      downloadLabel: null,
    },
  ],
  stillWorks: [
    'Add documents to Knowledge — reading and indexing them needs no model',
    'Browse Memory, Work, Projects and the egress log',
  ],
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

  it('does not pretend to carry out what nothing can carry out yet', () => {
    const onExplore = vi.fn();
    render(<FirstRunPanel report={noEngine} onExplore={onExplore} onConnected={() => {}} />);

    // Greyed and stated, not silently inert. A button that takes a click and
    // does nothing is the worst thing on a first-run screen: the user concludes
    // the product is broken rather than unconfigured, which is the exact
    // impression this screen exists to prevent.
    //
    // `use_cloud_key` was on this list until 29 August 2026 and has been
    // removed because it now has an executor, not because the rule softened.
    // Installing an engine and pulling a model still have none.
    for (const kind of ['install_engine', 'pull_model']) {
      const button = offerButton(kind);
      if (!button) continue;
      expect(button).toBeDisabled();
      // And it says so in words. A greyed button explains nothing on its own,
      // and the detail line above it describes an action — "installs the
      // engine" — that this button does not perform.
      expect(button).toHaveAccessibleName(/can’t set this up for you yet/);
      button.click();
    }
    expect(onExplore).not.toHaveBeenCalled();
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
        },
      ],
    };
    render(<FirstRunPanel report={future} onExplore={() => {}} onConnected={() => {}} />);

    expect(screen.getByText('An offer this build has never heard of')).toBeInTheDocument();
    expect(offerButton('something_later')).toBeDisabled();
  });
});
