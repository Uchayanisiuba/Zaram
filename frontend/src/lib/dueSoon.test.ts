import { describe, expect, it } from 'vitest';

import type { Obligation } from '@/services/obligationsClient';
import { WITHIN_DAYS, alreadySaid, dueSoonNotice, rememberSaid } from './dueSoon';

const NOW = new Date(2026, 8, 14, 15, 0); // 14 September 2026, afternoon

function ob(id: string, due: string, extra: Partial<Obligation> = {}): Obligation {
  return {
    id,
    kind: 'payment',
    summary: `Invoice to Harbour Lane (${id})`,
    due,
    source_clause: { text: 'Payment within 30 days.', page: 1 } as unknown as Obligation['source_clause'],
    source_document_id: 'c:/docs/terms.pdf',
    direction: 'owed_to_user',
    status: 'open',
    amount: null,
    currency: 'GBP',
    superseded_by: null,
    ...extra,
  } as Obligation;
}

class MemoryStorage {
  private map = new Map<string, string>();
  getItem(k: string) {
    return this.map.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.map.set(k, v);
  }
}

describe('what falls due soon', () => {
  it('names the week, nearest first, in one notice', () => {
    const notice = dueSoonNotice(
      [ob('a', '2026-09-20'), ob('b', '2026-09-15'), ob('c', '2026-10-30')],
      NOW,
      new Set(),
    );
    expect(notice).not.toBeNull();
    expect(notice!.title).toBe('2 commitments due this week');
    expect(notice!.body.split('\n')[0]).toContain('(b) — tomorrow');
    expect(notice!.body).toContain('(a) — in 6 days');
    expect(notice!.body).not.toContain('(c)');
    expect(notice!.ids).toEqual(['b', 'a']);
  });

  it('says past due when something has lapsed', () => {
    const notice = dueSoonNotice([ob('late', '2026-09-12')], NOW, new Set());
    expect(notice!.title).toBe('1 commitment is past due');
    expect(notice!.body).toContain('2 days ago');
  });

  it('is silent when there is nothing real to say', () => {
    expect(dueSoonNotice([], NOW, new Set())).toBeNull();
    expect(dueSoonNotice([ob('far', '2026-12-01')], NOW, new Set())).toBeNull();
    expect(dueSoonNotice([ob('met', '2026-09-15', { status: 'met' } as Partial<Obligation>)], NOW, new Set())).toBeNull();
    expect(dueSoonNotice([ob('old', '2026-09-15', { superseded_by: 'new' })], NOW, new Set())).toBeNull();
    expect(dueSoonNotice([ob('undated', 'within 30 days')], NOW, new Set())).toBeNull();
  });

  it('says each thing once a day, and again tomorrow if still open', () => {
    const storage = new MemoryStorage();
    const first = dueSoonNotice([ob('a', '2026-09-16')], NOW, alreadySaid(NOW, storage));
    rememberSaid(first!.ids, NOW, storage);

    expect(dueSoonNotice([ob('a', '2026-09-16')], NOW, alreadySaid(NOW, storage))).toBeNull();

    const tomorrow = new Date(2026, 8, 15, 9, 0);
    expect(dueSoonNotice([ob('a', '2026-09-16')], tomorrow, alreadySaid(tomorrow, storage))).not.toBeNull();
  });

  it('survives storage that is absent or broken', () => {
    expect(alreadySaid(NOW, null).size).toBe(0);
    const broken = { getItem: () => '{not json' } as unknown as Storage;
    expect(alreadySaid(NOW, broken).size).toBe(0);
    expect(() => rememberSaid(['a'], NOW, null)).not.toThrow();
  });

  it('the window is a week', () => {
    expect(WITHIN_DAYS).toBe(7);
  });
});
