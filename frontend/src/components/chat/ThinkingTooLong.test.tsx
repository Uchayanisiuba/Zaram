/**
 * @vitest-environment jsdom
 *
 * The offer to stop thinking appears at the moment of doubt, and not before.
 *
 * Rule 7h: offer when it is wanted, cost nothing when it is not. So the whole
 * contract is *when* it is drawn: not for an ordinary question, not once the
 * answer has begun, and not for a reply that has not started thinking.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import ThinkingTooLong, { OFFER_AFTER_MS, elapsedLabel } from './ThinkingTooLong';

afterEach(() => cleanup());

const at = (ms: number) => () => 1_000_000 + ms;
const SINCE = 1_000_000;

describe('when it is drawn', () => {
  it('is not drawn for a reply that has not started thinking', () => {
    render(<ThinkingTooLong since={null} answering={false} onSkip={() => {}} />);
    expect(screen.queryByTestId('thinking-too-long')).toBeNull();
  });

  it('is not drawn while thinking is still short', () => {
    render(<ThinkingTooLong since={SINCE} answering={false} onSkip={() => {}} now={at(OFFER_AFTER_MS - 1)} />);
    expect(screen.queryByTestId('thinking-too-long')).toBeNull();
  });

  it('is drawn once thinking has run past the threshold', () => {
    render(<ThinkingTooLong since={SINCE} answering={false} onSkip={() => {}} now={at(OFFER_AFTER_MS)} />);
    expect(screen.getByTestId('thinking-too-long')).toHaveTextContent('Still thinking');
  });

  it('is gone as soon as the answer has begun, however long the thinking was', () => {
    render(<ThinkingTooLong since={SINCE} answering onSkip={() => {}} now={at(10 * 60_000)} />);
    expect(screen.queryByTestId('thinking-too-long')).toBeNull();
  });

  it('says how long, so the wait is something the person can read', () => {
    render(<ThinkingTooLong since={SINCE} answering={false} onSkip={() => {}} now={at(125_000)} />);
    expect(screen.getByTestId('thinking-too-long')).toHaveTextContent('2m 05s so far');
  });

  it('keeps counting without being re-rendered by its parent', async () => {
    vi.useFakeTimers();
    try {
      let t = SINCE + OFFER_AFTER_MS;
      render(<ThinkingTooLong since={SINCE} answering={false} onSkip={() => {}} now={() => t} />);
      expect(screen.getByTestId('thinking-too-long')).toHaveTextContent('45s so far');
      t += 5000;
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1100);
      });
      expect(screen.getByTestId('thinking-too-long')).toHaveTextContent('50s so far');
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('what it offers', () => {
  it('asks again, for this message only — and says so', () => {
    render(<ThinkingTooLong since={SINCE} answering={false} onSkip={() => {}} now={at(60_000)} />);
    expect(screen.getByTestId('thinking-too-long')).toHaveTextContent('for this message only');
  });

  it('calls the handler when pressed', async () => {
    const onSkip = vi.fn();
    render(<ThinkingTooLong since={SINCE} answering={false} onSkip={onSkip} now={at(60_000)} />);
    await userEvent.setup().click(screen.getByTestId('skip-thinking'));
    expect(onSkip).toHaveBeenCalledTimes(1);
  });

  it('does not say the thinking was wasted', () => {
    render(<ThinkingTooLong since={SINCE} answering={false} onSkip={() => {}} now={at(60_000)} />);
    expect(screen.getByTestId('thinking-too-long').textContent ?? '').not.toMatch(/waste|slow|stuck|broken/i);
  });
});

describe('elapsedLabel', () => {
  it.each([
    [0, '0s'],
    [999, '0s'],
    [59_000, '59s'],
    [60_000, '1m 00s'],
    [125_000, '2m 05s'],
    [-5, '0s'],
  ])('%i ms is %s', (ms, label) => {
    expect(elapsedLabel(ms)).toBe(label);
  });
});
