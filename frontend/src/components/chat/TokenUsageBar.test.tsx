/**
 * The token counter: what it shows, and the three things it refuses to show.
 *
 * Asked for against a screenshot of Claude Code, whose header carries
 * `+8,507 −154`. That is a diff stat and Zaram has no diffs — every mutative
 * tool is out of scope until v1 — so the shape is borrowed and the quantity is
 * the real one: tokens sent and generated, against tokens a compaction took
 * back out.
 *
 * What is asserted here is mostly what it declines to draw. A counter is the
 * easiest thing in an interface to make dishonest, because a plausible number
 * looks exactly like a true one.
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

import { TokenUsageBar } from './TokenUsageBar';
import { useChatStore } from '@/stores/chatStore';

const setUsage = (usage: Partial<ReturnType<typeof useChatStore.getState>['turnUsage']>) =>
  useChatStore.setState({
    turnUsage: { added: 0, reclaimed: 0, limit: null, measured: false, ...usage },
  });

beforeEach(() => {
  setUsage({});
  useChatStore.setState({ isStreaming: false });
});
afterEach(cleanup);

describe('what it shows', () => {
  it('reports what the exchange added, grouped so it reads as a magnitude', () => {
    setUsage({ added: 12431 });
    render(<TokenUsageBar />);
    expect(screen.getByText('+12,431')).toBeTruthy();
  });

  it('shows the reclaimed half only when a compaction actually happened', () => {
    setUsage({ added: 9000 });
    const { rerender } = render(<TokenUsageBar />);
    expect(screen.queryByText(/−/)).toBeNull();

    setUsage({ added: 9000, reclaimed: 3200 });
    rerender(<TokenUsageBar />);
    // A real subtraction: the task carried itself into a fresh window and
    // dropped its oldest tool results, which removes them from the next
    // request. Not a display of a saving — the saving.
    expect(screen.getByText('−3,200')).toBeTruthy();
  });

  it('names the share of the window when the window was measured', () => {
    setUsage({ added: 8192, limit: 16384, measured: true });
    render(<TokenUsageBar />);
    expect(screen.getByText('50% of 16,384')).toBeTruthy();
  });
});

describe('what it refuses to show', () => {
  it('renders nothing at all before the first exchange', () => {
    // Not a row of zeroes. "Nothing was spent" and "nothing has been spent
    // yet" are different claims, and only one of them is true on a fresh
    // conversation.
    const { container } = render(<TokenUsageBar />);
    expect(container.firstChild).toBeNull();
  });

  it('never quotes a window it did not measure', () => {
    // `ContextBudget` falls back to a constant when it cannot read a model's
    // real `num_ctx` from `/api/ps`. Drawing a percentage against that would
    // state the fallback as a fact about the user's machine — the failure
    // `vram_bytes` refuses by returning null rather than zero.
    setUsage({ added: 8192, limit: 16384, measured: false });
    render(<TokenUsageBar />);
    expect(screen.queryByText(/% of/)).toBeNull();
    expect(screen.getByText('+8,192')).toBeTruthy();
  });

  it('does not divide by a window reported as zero', () => {
    setUsage({ added: 500, limit: 0, measured: true });
    render(<TokenUsageBar />);
    // Zero is not a small window, it is an unreadable one, and a share drawn
    // against it would report every conversation as full.
    expect(screen.queryByText(/% of/)).toBeNull();
  });
});
