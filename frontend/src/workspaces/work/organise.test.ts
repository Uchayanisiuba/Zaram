/**
 * Where each file lands, and the boundaries where that is easy to get wrong.
 *
 * Grouping is the part of Work's layout with right answers rather than
 * judgements, which is why it is a module rather than a `useMemo`. Three of the
 * cases below are ones an implementation gets wrong silently — a file made late
 * last night filed under Today, `image-10` sorted before `image-2`, and an
 * empty heading reading as "your invoices are gone".
 */
import { describe, expect, it } from 'vitest';

import type { Artifact, ArtifactKind } from '@/services/artifactsClient';

import { comparator, dateBucket, group, search } from './organise';

/** Epoch seconds for a local wall-clock moment. */
const at = (y: number, m: number, d: number, h = 12, min = 0) =>
  new Date(y, m - 1, d, h, min, 0, 0).getTime() / 1000;

const NOW = new Date(2026, 8, 7, 10, 30).getTime(); // 7 September 2026, 10:30

function art(over: Partial<Artifact> & { id: string }): Artifact {
  return {
    filename: `${over.id}.pdf`,
    kind: 'document' as ArtifactKind,
    project_id: '',
    origin: 'generated',
    created_at: at(2026, 9, 7),
    size_bytes: 1000,
    path: null,
    conversation_id: 'c1',
    conversation_title: '',
    sources: [],
    claims: [],
    indexed: true,
    remember_override: null,
    exists: true,
    ...over,
  } as Artifact;
}

describe('which day bucket a file lands in', () => {
  it('uses calendar days, not elapsed hours', () => {
    // **The case that is wrong in every naive implementation.** A file made at
    // 23:58 last night is two and a half hours old at 10:30 this morning, so
    // an hours-based rule calls it "Today" — for another twenty-three hours.
    // Nobody reports that; it just makes the list feel unreliable.
    expect(dateBucket(at(2026, 9, 6, 23, 58), NOW)).toBe('Yesterday');
  });

  it('calls a file from a minute ago today', () => {
    expect(dateBucket(at(2026, 9, 7, 10, 29), NOW)).toBe('Today');
  });

  it('calls midnight this morning today', () => {
    expect(dateBucket(at(2026, 9, 7, 0, 1), NOW)).toBe('Today');
  });

  it.each([
    [at(2026, 9, 4), 'Earlier this week'],
    [at(2026, 8, 25), 'Earlier this month'],
    [at(2026, 3, 2), 'Earlier this year'],
    [at(2024, 1, 2), 'Older'],
  ])('files older things further back', (when, expected) => {
    expect(dateBucket(when, NOW)).toBe(expected);
  });

  it('puts a file dated in the future in the newest bucket', () => {
    // A clock disagreement — a machine whose time moved, or a record written
    // by another device. "Later" is a heading nobody can act on, and inventing
    // one would be a claim about when a file will exist.
    expect(dateBucket(at(2027, 1, 1), NOW)).toBe('Today');
  });
});

describe('grouping', () => {
  const mixed = [
    art({ id: 'a', kind: 'image', created_at: at(2026, 9, 7) }),
    art({ id: 'b', kind: 'invoice', created_at: at(2026, 9, 6) }),
    art({ id: 'c', kind: 'invoice', created_at: at(2026, 5, 1) }),
  ];

  it('emits no empty headings', () => {
    // A heading with nothing under it claims the bucket exists and is empty,
    // which on this surface reads as "your spreadsheets are gone" rather than
    // "you have not made any".
    const groups = group(mixed, 'type', 'newest', NOW);
    expect(groups.map((g) => g.key)).toEqual(['invoice', 'image']);
    expect(groups.every((g) => g.artifacts.length > 0)).toBe(true);
  });

  it('orders type groups the way the kind map declares them', () => {
    // Read from `KIND_LABELS` rather than restated, so a new kind appears
    // without touching the grouping. A second copy of a kind map is how `deck`
    // and `cv` shipped with no icon in Work.
    expect(group(mixed, 'type', 'newest', NOW).map((g) => g.label)).toEqual([
      'Invoices',
      'Images',
    ]);
  });

  it('orders date groups newest first', () => {
    expect(group(mixed, 'date', 'newest', NOW).map((g) => g.label)).toEqual([
      'Today',
      'Yesterday',
      'Earlier this year',
    ]);
  });

  it('puts the unassigned project last, not first', () => {
    // `''` sorts before every real name, which would put "No project" at the
    // top where it reads as the most important group on the surface.
    const rows = [
      art({ id: 'x', project_id: '' }),
      art({ id: 'y', project_id: 'northwind' }),
      art({ id: 'z', project_id: 'acme' }),
    ];
    expect(group(rows, 'project', 'newest', NOW).map((g) => g.label)).toEqual([
      'acme',
      'northwind',
      'No project',
    ]);
  });

  it('does not prettify a project id', () => {
    // A slug turned into a title is a value nobody entered.
    const rows = [art({ id: 'x', project_id: 'north_wind-2026' })];
    expect(group(rows, 'project', 'newest', NOW)[0].label).toBe('north_wind-2026');
  });

  it('returns one unlabelled group when grouping is off', () => {
    // One code path for the caller. A second rendering branch for the
    // ungrouped case is how the two come to disagree about row markup.
    const groups = group(mixed, 'none', 'newest', NOW);
    expect(groups).toHaveLength(1);
    expect(groups[0].label).toBe('');
    expect(groups[0].artifacts).toHaveLength(3);
  });

  it('returns nothing at all for an empty listing', () => {
    expect(group([], 'none', 'newest', NOW)).toEqual([]);
    expect(group([], 'type', 'newest', NOW)).toEqual([]);
  });

  it('sorts inside each group, not only across them', () => {
    const rows = [
      art({ id: 'old', kind: 'invoice', created_at: at(2026, 9, 1) }),
      art({ id: 'new', kind: 'invoice', created_at: at(2026, 9, 5) }),
    ];
    expect(group(rows, 'type', 'newest', NOW)[0].artifacts.map((a) => a.id)).toEqual([
      'new',
      'old',
    ]);
    expect(group(rows, 'type', 'oldest', NOW)[0].artifacts.map((a) => a.id)).toEqual([
      'old',
      'new',
    ]);
  });

  it('does not reorder the caller’s array', () => {
    const rows = [art({ id: 'b', created_at: 2 }), art({ id: 'a', created_at: 9 })];
    group(rows, 'none', 'newest', NOW);
    expect(rows.map((a) => a.id)).toEqual(['b', 'a']);
  });
});

describe('sorting by name', () => {
  it('puts image-2 before image-10', () => {
    // Plain string order puts `image-10` first. Zaram names its own output with
    // trailing numbers, so this is the one place a filename list is obviously
    // wrong to anybody scanning it.
    const rows = [
      art({ id: 'ten', filename: 'image-10.png' }),
      art({ id: 'two', filename: 'image-2.png' }),
    ].sort(comparator('name'));
    expect(rows.map((a) => a.filename)).toEqual(['image-2.png', 'image-10.png']);
  });

  it('ignores case', () => {
    const rows = [art({ id: 'b', filename: 'Zebra.pdf' }), art({ id: 'a', filename: 'apple.pdf' })].sort(
      comparator('name'),
    );
    expect(rows.map((a) => a.filename)).toEqual(['apple.pdf', 'Zebra.pdf']);
  });
});

describe('search', () => {
  const rows = [
    art({ id: '1', filename: 'invoice-0007.pdf', conversation_title: 'Northwind rate change' }),
    art({ id: '2', filename: 'notes.docx', conversation_title: 'Acme kickoff', project_id: 'acme' }),
  ];

  it('finds a file by the conversation that made it', () => {
    // The reason this surface is not a file browser. Somebody looking for "the
    // invoice for the Northwind job" remembers the job, not `invoice-0007.pdf`.
    expect(search(rows, 'northwind').map((a) => a.id)).toEqual(['1']);
  });

  it('finds a file by its project', () => {
    expect(search(rows, 'acme').map((a) => a.id)).toEqual(['2']);
  });

  it('finds a file by name', () => {
    expect(search(rows, '0007').map((a) => a.id)).toEqual(['1']);
  });

  it('ignores case and surrounding space', () => {
    expect(search(rows, '  NORTHWIND ').map((a) => a.id)).toEqual(['1']);
  });

  it('returns everything for an empty query', () => {
    // Not nothing. An empty search box is not a filter that excludes all.
    expect(search(rows, '')).toHaveLength(2);
    expect(search(rows, '   ')).toHaveLength(2);
  });
});
