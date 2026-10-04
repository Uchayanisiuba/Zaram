/**
 * The overflow choice and the reply cap.
 *
 * The last two of LM Studio's four token controls. These assert the
 * parts a backend test cannot reach: that the choice is framed by what
 * it costs rather than by what it is called, and that the two numbers
 * are told apart on screen — the window is the whole pool, the cap
 * bounds one reply, and confusing them is the obvious mistake.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ComponentProps } from 'react';
import { describe, expect, it, vi } from 'vitest';

import OverflowField from './OverflowField';

type Props = ComponentProps<typeof OverflowField>;

function field(props: Partial<Props> = {}) {
  return (
    <OverflowField
      policy="trim"
      cap={0}
      onChoosePolicy={vi.fn()}
      onChooseCap={vi.fn()}
      {...props}
    />
  );
}

async function open() {
  await userEvent.click(screen.getByText('Advanced'));
}

describe('what happens when it runs out', () => {
  it('offers both, with trimming marked by default', async () => {
    render(field());
    await open();
    expect(screen.getByTestId('overflow-trim')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('overflow-stop')).toHaveAttribute('aria-pressed', 'false');
  });

  it('says when each one is the wrong choice, not only what it does', async () => {
    /** The part nobody can see. "Drop the oldest exchanges" without
     *  *"wrong when the answer depends on something said at the very
     *  start"* is a name, and the whole reason `stop` exists is that
     *  case. */
    render(field());
    await open();
    expect(screen.getByTestId('overflow-trim')).toHaveTextContent('said at the very start');
    expect(screen.getByTestId('overflow-stop')).toHaveTextContent('must stay in view');
  });

  it('reports the choice when one is made', async () => {
    const onChoosePolicy = vi.fn();
    render(field({ onChoosePolicy }));
    await open();
    await userEvent.click(screen.getByTestId('overflow-stop'));
    expect(onChoosePolicy).toHaveBeenCalledWith('stop');
  });

  it('marks the one in force', async () => {
    render(field({ policy: 'stop' }));
    await open();
    expect(screen.getByTestId('overflow-stop')).toHaveAttribute('aria-pressed', 'true');
  });
});

describe('the longest single reply', () => {
  it('is uncapped by default, and says so in words', async () => {
    // Not "0". A quarter of the window is already reserved for the
    // reply, so the honest label is what happens, not the number.
    render(field());
    await open();
    expect(screen.getByTestId('reply-cap-0')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('reply-cap-0')).toHaveTextContent('As long as it needs');
  });

  it('offers short caps, because that is what anybody sets this for', async () => {
    /** A cap of 32k on a 32k window does nothing. The reason to reach
     *  for this is to stop a model writing an essay when a sentence was
     *  wanted, so the useful end of the range is the small end. */
    render(field());
    await open();
    expect(screen.getByTestId('reply-cap-256')).toBeTruthy();
    expect(screen.getByTestId('reply-cap-512')).toBeTruthy();
  });

  it('reports a cap when one is chosen', async () => {
    const onChooseCap = vi.fn();
    render(field({ onChooseCap }));
    await open();
    await userEvent.click(screen.getByTestId('reply-cap-1024'));
    expect(onChooseCap).toHaveBeenCalledWith(1_024);
  });

  it('marks the cap in force', async () => {
    render(field({ cap: 2_048 }));
    await open();
    expect(screen.getByTestId('reply-cap-2048')).toHaveAttribute('aria-pressed', 'true');
  });

  it('tells it apart from the context window in as many words', async () => {
    /** The two are easy to confuse and sit next to each other, so the
     *  difference is stated rather than implied. */
    render(field());
    await open();
    expect(screen.getByTestId('reply-cap')).toHaveTextContent('whole pool');
    expect(screen.getByTestId('reply-cap')).toHaveTextContent('bounds the reply alone');
  });

  it('warns that a short cap stops mid-sentence', async () => {
    // A model cut off at 256 tokens has not finished early, it has
    // stopped. Somebody choosing the smallest option should know that
    // before they choose it rather than after.
    render(field());
    await open();
    expect(screen.getByTestId('reply-cap')).toHaveTextContent('mid-sentence');
  });
});
