/**
 * Zaram's own manual is never offered as if it were your folder.
 *
 * Reported 28 September 2026 with a screenshot: the first thing the empty
 * conversation offered was **"What is in zaram-manual, in a few lines?"**, and
 * it did not answer.
 *
 * Two faults compounding, and neither is the model's.
 *
 * Zaram ships its own manual and `manual.ensure_indexed` reads it at start,
 * again whenever a page changes. `groundedPrompts` picks the *most recently
 * scanned* source — so on a fresh machine, and after every manual update, the
 * folder prompt is about the manual. This module's own header says these
 * prompts are about "the person's own folder", and the manual is not that.
 *
 * And the question could not be served anyway. A source's `name` is the
 * basename of its directory, so "zaram-manual" is a folder name; the pages
 * themselves say "Zaram" and never that. Similarity recall was matching a
 * directory against prose that never uses it — rule 9's referential failure,
 * offered to a person before they had typed anything.
 */
import { describe, expect, it } from 'vitest';

import { groundedPrompts } from './groundedPrompts';
import type { IngestSource } from '@/services/ingestClient';

const source = (over: Partial<IngestSource>): IngestSource =>
  ({
    id: 'src-1',
    root: 'C:\\Users\\me\\Contracts',
    name: 'Contracts',
    added_at: 1_700_000_000,
    scanned_at: 1_700_000_000,
    seconds: 1,
    policy: 'local_only',
    notified: true,
    counts: { indexed: 4 },
    total: 4,
    problems: 0,
    staged: false,
    builtin: false,
    ...over,
  }) as IngestSource;

const NOW = 1_700_000_400;

describe('the folder prompt is about the person’s own material', () => {
  it('never offers Zaram’s own manual, however recently it was read', () => {
    const prompts = groundedPrompts(
      {
        obligations: null,
        sources: [
          source({ id: 'manual', name: 'zaram-manual', builtin: true, scanned_at: NOW }),
          source({ scanned_at: 1_700_000_000 }),
        ],
        projects: null,
      },
      NOW,
    );
    expect(prompts.some((p) => p.prompt.includes('zaram-manual'))).toBe(false);
  });

  it('falls through to the person’s folder instead of going quiet', () => {
    const prompts = groundedPrompts(
      {
        obligations: null,
        sources: [
          source({ id: 'manual', name: 'zaram-manual', builtin: true, scanned_at: NOW }),
          source({ name: 'Contracts', scanned_at: 1_700_000_000 }),
        ],
        projects: null,
      },
      NOW,
    );
    expect(prompts.some((p) => p.prompt.includes('Contracts'))).toBe(true);
  });

  it('offers nothing rather than the manual when the manual is all there is', () => {
    // A fresh install. The starter tasks answer "what is this for" here; a
    // prompt about a folder the person has never heard of does not.
    const prompts = groundedPrompts(
      {
        obligations: null,
        sources: [source({ id: 'manual', name: 'zaram-manual', builtin: true })],
        projects: null,
      },
      NOW,
    );
    expect(prompts).toEqual([]);
  });

  it('still offers a folder the person happens to have named zaram-manual', () => {
    // The backend decides this from the id it recorded. Matching on the name
    // would take somebody's own folder away from them.
    const prompts = groundedPrompts(
      {
        obligations: null,
        sources: [source({ name: 'zaram-manual', builtin: false })],
        projects: null,
      },
      NOW,
    );
    expect(prompts.some((p) => p.prompt.includes('zaram-manual'))).toBe(true);
  });
});
