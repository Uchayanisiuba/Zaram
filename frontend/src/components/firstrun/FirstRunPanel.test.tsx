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
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} />);

    expect(screen.getByText(noEngine.summary)).toBeInTheDocument();
  });

  it('puts the download size on the button, not behind a tooltip', () => {
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} />);

    // Read off the accessible name: a size in a `title` or a hover card is a
    // price the user has to go looking for, which is not a price stated.
    expect(offerButton('install_engine')).toHaveAccessibleName(/1\.1 GB/);
  });

  it('shows no size at all when nothing is downloaded', () => {
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} />);

    // Not "0 MB". Zero is a figure and it reads as free rather than as absent.
    expect(offerButton('use_cloud_key').textContent).not.toMatch(/\d+\s*(MB|GB)/);
    expect(offerButton('explore').textContent).not.toMatch(/\d+\s*(MB|GB)/);
  });

  it('names what still works, so the screen reads as unconfigured not broken', () => {
    render(<FirstRunPanel report={noEngine} onExplore={() => {}} />);

    for (const line of noEngine.stillWorks) {
      expect(screen.getByText(line)).toBeInTheDocument();
    }
  });

  it('offers the way out that it can actually honour', async () => {
    const onExplore = vi.fn();
    render(<FirstRunPanel report={noEngine} onExplore={onExplore} />);

    offerButton('explore').click();

    expect(onExplore).toHaveBeenCalledTimes(1);
  });

  it('does not pretend to carry out what nothing can carry out yet', () => {
    const onExplore = vi.fn();
    render(<FirstRunPanel report={noEngine} onExplore={onExplore} />);

    // Greyed and stated, not silently inert. A button that takes a click and
    // does nothing is the worst thing on a first-run screen: the user concludes
    // the product is broken rather than unconfigured, which is the exact
    // impression this screen exists to prevent.
    for (const kind of ['install_engine', 'use_cloud_key']) {
      expect(offerButton(kind)).toBeDisabled();
      // And it says so in words. A greyed button explains nothing on its own,
      // and the detail line above it describes an action — "installs the
      // engine" — that this button does not perform.
      expect(offerButton(kind)).toHaveAccessibleName(/can’t set this up for you yet/);
      offerButton(kind).click();
    }
    expect(onExplore).not.toHaveBeenCalled();
  });

  it('composes no model filenames of its own', () => {
    // The payload is asserted clean on the backend side. This asserts the
    // component adds nothing — an "e.g. …" in a detail line would be the
    // obvious, helpful-looking way to reintroduce them.
    const { container } = render(<FirstRunPanel report={noEngine} onExplore={() => {}} />);

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
    render(<FirstRunPanel report={future} onExplore={() => {}} />);

    expect(screen.getByText('An offer this build has never heard of')).toBeInTheDocument();
    expect(offerButton('something_later')).toBeDisabled();
  });
});
