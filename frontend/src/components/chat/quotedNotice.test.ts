/**
 * The quoted-passage disclosure is quiet, and it is never gone.
 *
 * Both halves matter and they pull against each other, which is why they are
 * tested together. It used to be an amber warning triangle across the reply —
 * wrong, because nothing went wrong and nothing is asked of the reader, and
 * `NoticeCard`'s own header already says what spending the amber one on
 * routine housekeeping costs. But `core/untrusted.py` is equally explicit that
 * the scan reports rather than filters, *"because a filter that quietly
 * removes things trains nobody"*. So: demoted in loudness, never in reach.
 */
import { describe, it, expect } from 'vitest';
import { splitQuotedNotice, QUOTED_KIND } from './quotedNotice';
import type { ChatNotice } from '../../stores/chatStore';

const notice = (kind: string, content = 'something'): ChatNotice => ({
  content,
  kind,
  action: 'knowledge',
});

describe('splitQuotedNotice', () => {
  it('takes the quoted-passage notice out of the cards', () => {
    const { cards, quoted } = splitQuotedNotice([
      notice('domain'),
      notice(QUOTED_KIND, 'reads like an instruction rather than a record'),
      notice('attachment'),
    ]);

    expect(cards.map((n) => n.kind)).toEqual(['domain', 'attachment']);
    expect(quoted?.content).toBe('reads like an instruction rather than a record');
  });

  it('carries the backend’s own wording rather than a second copy of it', () => {
    // A sentence rewritten in the interface is the one that drifts when the
    // backend's changes.
    const { quoted } = splitQuotedNotice([notice(QUOTED_KIND, 'exact backend wording')]);
    expect(quoted?.content).toBe('exact backend wording');
  });

  it('leaves every other notice exactly as it was', () => {
    const notices = [notice('domain'), notice('attachment'), notice('images')];
    const { cards, quoted } = splitQuotedNotice(notices);
    expect(cards).toHaveLength(3);
    expect(quoted).toBeNull();
  });

  it('handles a reply with no notices at all', () => {
    expect(splitQuotedNotice(undefined)).toEqual({ cards: [], quoted: null });
    expect(splitQuotedNotice([])).toEqual({ cards: [], quoted: null });
  });

  it('never drops it: a caller with nowhere to put it still gets it back', () => {
    // The reply that cited nothing has no sources line to ride, and
    // `ChatSurface` falls back to rendering the card. That fallback is only
    // possible because the notice survives the split.
    const { quoted } = splitQuotedNotice([notice(QUOTED_KIND)]);
    expect(quoted).not.toBeNull();
  });
});
