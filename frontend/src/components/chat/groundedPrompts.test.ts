import { describe, it, expect } from 'vitest';
import { groundedPrompts } from './groundedPrompts';
import type { IngestSource } from '@/services/ingestClient';
import type { Project } from '@/stores/projectStore';

const NOW = 1_800_000_000;

const source = (over: Partial<IngestSource>): IngestSource => ({
  id: 's1',
  root: 'C:/Clients/Abuja',
  name: 'Abuja',
  added_at: NOW - 86_400,
  scanned_at: NOW - 86_400,
  seconds: 3,
  policy: 'local_only',
  notified: false,
  counts: {},
  total: 12,
  problems: 0,
  staged: false,
  ...over,
});

const project = (over: Partial<Project>): Project =>
  ({
    id: 'p1',
    name: 'Abuja fit-out',
    type: 'general',
    created_at: NOW,
    note: '',
    scope: 'project:p1',
    root: '',
    runs: false,
    artifacts: 0,
    facts: 11,
    ...over,
  }) as Project;

describe('the empty conversation offers only what is there', () => {
  it('offers nothing when nothing is indexed — no invented example', () => {
    expect(groundedPrompts({ obligations: null, sources: null, projects: null }, NOW)).toEqual([]);
    expect(
      groundedPrompts(
        { obligations: { open: 0, overdue: 0, questions: 0 }, sources: [], projects: [project({ facts: 0 })] },
        NOW,
      ),
    ).toEqual([]);
  });

  it('grounds each prompt in a measurement, and says which', () => {
    const prompts = groundedPrompts(
      {
        obligations: { open: 3, overdue: 1, questions: 0 },
        sources: [source({})],
        projects: [project({})],
      },
      NOW,
    );
    expect(prompts).toEqual([
      {
        prompt: 'What do I owe, and what am I owed, this month?',
        reason: '3 open obligations in your documents · 1 overdue',
      },
      { prompt: 'What is in Abuja, in a few lines?', reason: '12 files read yesterday' },
      { prompt: 'What has been decided on Abuja fit-out so far?', reason: '11 facts scoped to that project' },
    ]);
  });

  it('picks the most recently read folder and the project with most facts', () => {
    const prompts = groundedPrompts(
      {
        obligations: null,
        sources: [source({ name: 'Old', scanned_at: NOW - 30 * 86_400 }), source({ id: 's2', name: 'Lagos', scanned_at: NOW })],
        projects: [project({ name: 'Small', facts: 2 }), project({ id: 'p2', name: 'Big', facts: 40 })],
      },
      NOW,
    );
    expect(prompts.map((p) => p.prompt)).toEqual([
      'What is in Lagos, in a few lines?',
      'What has been decided on Big so far?',
    ]);
    expect(prompts[0].reason).toBe('12 files read today');
  });

  it('leaves out a project the Spine could not count', () => {
    // -1 means unknown, not none — and unknown grounds nothing.
    expect(groundedPrompts({ obligations: null, sources: null, projects: [project({ facts: -1 })] }, NOW)).toEqual([]);
  });
});
