/**
 * When the embodiment says Zaram is coding, and when it must not.
 *
 * Asked for on 7 September 2026: a coding state the avatar follows. The whole
 * risk in a sixth state is *what it is derived from*, because the obvious
 * signal is the wrong one.
 *
 * **A coding model answering is a routing fact and must never reach a face.**
 * `local` and `cloud` were removed from this vocabulary on 13 August for that
 * reason — a face that reports where an answer came from is read as a someone,
 * and "she used the cloud" is the projection the embodiment rule exists to
 * prevent. So these assert on activity: the code tools ran, or the reply is
 * writing code. Both are things the system is *doing*.
 */
import { describe, it, expect } from 'vitest';

import { codingActivity, chatActivity, preserveSpeaking } from './orbActivity';

describe('when it says coding', () => {
  it('says coding once a fence opens in the reply', () => {
    // The literal thing that was asked for: Zaram writing code.
    expect(codingActivity(true, 'Here is the fix.\n\n```python\ndef f():')).toBe('coding');
  });

  it('says coding when the code tools ran, whatever the reply says', () => {
    // A repository being read is coding work even before a line is written,
    // and it is the state a user watches during the buffered pause.
    expect(codingActivity(true, 'Let me look.', ['code'])).toBe('coding');
  });

  it('stays coding after the block closes', () => {
    // A block that closes with prose after it has not stopped the exchange
    // being a coding exchange. A state that flickered mid-answer would read as
    // a fault rather than as a change.
    const reply = 'Here.\n\n```py\nx = 1\n```\n\nRun it against April.';
    expect(codingActivity(true, reply)).toBe('coding');
  });
});

describe('when it must not', () => {
  it('is only thinking for an ordinary reply', () => {
    expect(codingActivity(true, 'Your day rate for Harbour is six hundred pounds.')).toBe(
      'thinking',
    );
  });

  it('is idle when nothing is in flight, whatever the last reply held', () => {
    expect(codingActivity(false, '```py\nx = 1\n```')).toBe('idle');
  });

  it('does not read a fence out of inline code', () => {
    // A single backtick is not a block. `main.py` in a sentence is prose about
    // code, not code being written.
    expect(codingActivity(true, 'Open `main.py` and change `--strictPort`.')).toBe('thinking');
  });

  it('does not treat some other tool as coding', () => {
    expect(codingActivity(true, 'Reading that.', ['blender', 'unreal'])).toBe('thinking');
  });
});

describe('what it does not disturb', () => {
  it('narrows chatActivity rather than restating it', () => {
    // One place says "streaming means thinking, otherwise idle". If these two
    // ever disagreed, the orb and the avatar would disagree with them
    // differently — the divergence the shared table exists to stop.
    for (const streaming of [true, false]) {
      const base = chatActivity(streaming);
      const narrowed = codingActivity(streaming, 'ordinary prose');
      expect(narrowed).toBe(base);
    }
  });

  it('never lands on top of speech', () => {
    // Speech outlives the stream by design. `preserveSpeaking` is what stopped
    // the old `idle` clobbering it on every reply, and coding must not
    // reintroduce that — it is the reason the avatar's mouth never moved.
    expect(preserveSpeaking('speaking', codingActivity(true, '```py'))).toBe('speaking');
  });
});
