/**
 * What the download shows while it runs, and what it says when it stops.
 *
 * The percentage is the property worth guarding. It counts against the total
 * the *pull* reports, never the approximate figure the manifest quoted — a bar
 * that reaches 103% or stalls at 96% is worse than no bar, because the user
 * cannot tell it from a stall.
 */
import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';

import ModelPull from './ModelPull';
import { pullRecommendedModel, type PullEvent } from '@/services/pullClient';

vi.mock('@/services/pullClient', () => ({
  pullRecommendedModel: vi.fn(),
}));

const mocked = vi.mocked(pullRecommendedModel);

/** Replay a stream of events into the component's handler.
 *
 * Braces on both of these, deliberately. A hook body that *returns* something
 * callable is registered by Vitest as a cleanup hook and invoked after the
 * test — so `beforeEach(() => mocked.mockReset())` had the runner calling the
 * mock itself, with no arguments, and every test failed inside its own stub
 * with `onEvent is not a function`. The error pointed at the stub, which is
 * the last place the cause was.
 */
const replays = (...events: PullEvent[]) => {
  mocked.mockImplementation(async (onEvent) => {
    for (const event of events) onEvent(event);
  });
};

beforeEach(() => {
  mocked.mockReset();
});
afterEach(cleanup);

const start = () => (screen.getByText('Start the download') as HTMLButtonElement).click();

describe('the model download', () => {
  it('asks for nothing until the user starts it', () => {
    replays();
    render(<ModelPull onFinished={() => {}} />);

    expect(mocked).not.toHaveBeenCalled();
    expect(screen.getByText('Start the download')).toBeInTheDocument();
  });

  it('counts against the total the pull reports', async () => {
    replays({ stage: 'Downloading', completed: 25, total: 100 });
    render(<ModelPull onFinished={() => {}} />);

    start();

    expect(await screen.findByText('25%')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '25');
  });

  it('shows no percentage before there is a total to count against', async () => {
    // "Looking it up" carries no bytes. A percentage here would be a number
    // the user watches instead of the truth.
    replays({ stage: 'Looking it up' });
    render(<ModelPull onFinished={() => {}} />);

    start();

    expect(await screen.findByText('Looking it up')).toBeInTheDocument();
    expect(screen.queryByText(/%$/)).not.toBeInTheDocument();
    expect(screen.getByRole('progressbar')).not.toHaveAttribute('aria-valuenow');
  });

  it('tells whoever is listening when it is done', async () => {
    const onFinished = vi.fn();
    replays({ stage: 'Downloading', completed: 2, total: 2 }, { done: true });
    render(<ModelPull onFinished={onFinished} />);

    start();

    await waitFor(() => expect(onFinished).toHaveBeenCalledTimes(1));
  });

  it('says what went wrong and leaves a way to try again', async () => {
    // A download that dies at 80% on a metered connection is the worst moment
    // in this product to be vague.
    replays({ stage: 'Downloading', completed: 8, total: 10 }, { error: 'disk full' });
    render(<ModelPull onFinished={() => {}} />);

    start();

    expect(await screen.findByText(/disk full/)).toBeInTheDocument();
    expect(screen.getByText('Try again')).toBeInTheDocument();
  });

  it('does not report success when the stream failed', async () => {
    const onFinished = vi.fn();
    replays({ error: 'no route to host' });
    render(<ModelPull onFinished={onFinished} />);

    start();

    await screen.findByText(/no route to host/);
    expect(onFinished).not.toHaveBeenCalled();
  });

  it('reports a request that never started at all', async () => {
    // A 503 before the body opens: the route answers with a status code, not
    // a stream, and the screen must still say something a person can act on.
    mocked.mockRejectedValue(new Error('the egress log is not ready'));
    render(<ModelPull onFinished={() => {}} />);

    start();

    expect(await screen.findByText(/the egress log is not ready/)).toBeInTheDocument();
  });
});
