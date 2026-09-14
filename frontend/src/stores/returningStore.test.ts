/**
 * The returning line: measured, omitted when unmeasured, empty when there is
 * nothing to say.
 */
import { describe, it, expect } from 'vitest';
import { returningSegments, sinceWord, type Returning } from './returningStore';

const NOW = Date.UTC(2026, 8, 14, 12, 0, 0) / 1000; // Monday 14 Sep 2026, midday

const full: Returning = {
  sinceAt: NOW - 3 * 86_400,
  newFacts: 14,
  totalFacts: 412,
  projects: 3,
  last: { id: 'c1', title: 'the Abuja fit-out' },
  bytesToday: 0,
};

const texts = (r: Returning) => returningSegments(r, NOW).map((s) => s.text);

describe('the returning line', () => {
  it('reads as one line of measured things, each a way in', () => {
    const segments = returningSegments(full, NOW);
    expect(segments.map((s) => s.text)).toEqual([
      '14 new facts since Friday',
      '3 projects',
      'last: the Abuja fit-out',
      '0 bytes out today',
    ]);
    expect(segments.map((s) => s.target)).toEqual(['memory', 'project', 'resume', 'activity']);
    expect(segments[2].conversationId).toBe('c1');
  });

  it('says nothing at all when nothing is remembered', () => {
    // The first-launch instruction takes the slot instead.
    expect(
      returningSegments(
        { sinceAt: null, newFacts: null, totalFacts: 0, projects: 0, last: null, bytesToday: 0 },
        NOW,
      ),
    ).toEqual([]);
  });

  it('omits a segment whose measurement failed, never rendering it as zero', () => {
    // The egress log unreachable is not "0 bytes left". A privacy claim made
    // from an absent measurement is the one false thing this line must not say.
    expect(texts({ ...full, bytesToday: null })).not.toContain('0 bytes out today');
    expect(texts({ ...full, projects: null })).toEqual([
      '14 new facts since Friday',
      'last: the Abuja fit-out',
      '0 bytes out today',
    ]);
  });

  it('falls back to the total on the first launch, when there is no since', () => {
    expect(texts({ ...full, sinceAt: null, newFacts: null })[0]).toBe('412 facts');
  });

  it('says a measured nothing plainly', () => {
    expect(texts({ ...full, newFacts: 0 })[0]).toBe('no new facts since Friday');
    expect(texts({ ...full, sinceAt: NOW - 600, newFacts: 0 })[0]).toBe('no new facts');
  });

  it('shortens a long conversation title rather than letting the line wrap into a paragraph', () => {
    const title = 'Write three short paragraphs about Biscuit, using what you remember about her.';
    const last = texts({ ...full, last: { id: 'c2', title } })[2];
    expect(last.length).toBeLessThan(title.length);
    expect(last.endsWith('…')).toBe(true);
  });
});

describe('since, in words', () => {
  it('names the day the way a person would', () => {
    expect(sinceWord(NOW - 3600, NOW)).toBe('earlier today');
    expect(sinceWord(NOW - 86_400, NOW)).toBe('yesterday');
    expect(sinceWord(NOW - 3 * 86_400, NOW)).toBe('Friday');
    expect(sinceWord(NOW - 20 * 86_400, NOW)).toBe('25 Aug');
  });
});
