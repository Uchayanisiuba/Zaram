import { describe, it, expect } from 'vitest';
import { clearsIn, clearsLabel } from './staging';

const HOUR = 3600;
const DAY = 24 * HOUR;
const NOW = 1_700_000_000;

describe('clearsIn', () => {
  it('counts whole days while there are days left', () => {
    expect(clearsIn(NOW + 7 * DAY, NOW)).toBe('in 7 days');
    expect(clearsIn(NOW + 1 * DAY, NOW)).toBe('in 1 day');
  });

  /** The regression the unit tests could not have caught, because they hand
   *  whole numbers in and get whole numbers back. A file staged one second ago
   *  has 6.9999 days left, and flooring made the card read "in 6 days" the
   *  instant it appeared — an off-by-one on the most common case there is.
   *  Found by looking at it. */
  it('says seven days for a file staged a moment ago', () => {
    expect(clearsIn(NOW + 7 * DAY - 0.001, NOW)).toBe('in 7 days');
    expect(clearsIn(NOW + 7 * DAY - 30, NOW)).toBe('in 7 days');
  });

  /** Rounding is safe here only because `sweep` runs daily: a file goes at the
   *  first sweep *after* its expiry, so there is up to a day of grace behind
   *  the number already. */
  it('rounds to the nearest day', () => {
    expect(clearsIn(NOW + 2 * DAY + 20 * HOUR, NOW)).toBe('in 3 days');
    expect(clearsIn(NOW + 2 * DAY + 2 * HOUR, NOW)).toBe('in 2 days');
  });

  it('floors hours, where rounding up would overstate the urgency', () => {
    expect(clearsIn(NOW + 5 * HOUR + 59 * 60, NOW)).toBe('in 5 hours');
  });

  /** Never "in 0 days" — the hours branch owns everything under a day, and the
   *  floor of 1 covers the sliver rounding could push below it. */
  it('never says zero of anything', () => {
    for (const seconds of [DAY, DAY + 1, 1.4 * DAY, 23 * HOUR]) {
      expect(clearsIn(NOW + seconds, NOW)).not.toContain(' 0 ');
    }
  });

  it('drops to hours inside the last day', () => {
    expect(clearsIn(NOW + 23 * HOUR, NOW)).toBe('in 23 hours');
    expect(clearsIn(NOW + 1 * HOUR, NOW)).toBe('in 1 hour');
  });

  /** Minutes would be a precision nothing here has — the sweep is daily — and
   *  a ticking number invites watching something that does not reward it. */
  it('says nothing precise under an hour', () => {
    expect(clearsIn(NOW + 59 * 60, NOW)).toBe('within the hour');
    expect(clearsIn(NOW + 1, NOW)).toBe('within the hour');
  });

  /** Due but not yet swept is a real state: the sweep runs daily, so a file
   *  can sit past its window. A negative duration rendered as one would be a
   *  number counting the wrong way. */
  it('never renders a negative duration', () => {
    expect(clearsIn(NOW - 1, NOW)).toBe('very soon');
    expect(clearsIn(NOW - 10 * DAY, NOW)).toBe('very soon');
    expect(clearsIn(NOW, NOW)).toBe('very soon');
  });

  it('defaults to the real clock without being handed one', () => {
    expect(clearsIn(Date.now() / 1000 + 3 * DAY)).toBe('in 3 days');
  });
});

describe('clearsLabel', () => {
  /** A countdown with no stated remedy reads as a threat. The way out belongs
   *  in the same breath as the deadline. */
  it('names the way out beside the deadline', () => {
    expect(clearsLabel(NOW + 7 * DAY, NOW)).toBe('clears in 7 days unless you save it');
  });

  it('reads as a sentence at every scale', () => {
    for (const seconds of [7 * DAY, 1 * DAY, 5 * HOUR, 1 * HOUR, 60, -1]) {
      const label = clearsLabel(NOW + seconds, NOW);
      expect(label.startsWith('clears ')).toBe(true);
      expect(label.endsWith(' unless you save it')).toBe(true);
      expect(label).not.toContain('NaN');
      expect(label).not.toContain('undefined');
      expect(label).not.toContain('-');
    }
  });
});
