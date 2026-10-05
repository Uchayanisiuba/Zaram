import { describe, it, expect } from 'vitest';
import { groundedPrompts } from './groundedPrompts';
import type { IngestSource } from '@/services/ingestClient';
import type { Project } from '@/stores/projectStore';
import type { UnfinishedTask } from '@/services/plansClient';
import type { ConversationSummary } from '@/services/conversationsClient';

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
    drives: false,
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

describe('what is unfinished comes first, in the project touched last', () => {
  const task = (over: Partial<UnfinishedTask>): UnfinishedTask => ({
    id: 't1',
    question: 'set it up',
    project_id: 'p1',
    model: '',
    stopped_because: '',
    steps: [],
    items: [],
    approved: false,
    finished: false,
    created_at: NOW - 5_000,
    updated_at: NOW - 3_600,
    ...over,
  });

  it('names the project and the measurement, and carries what picking it resumes', () => {
    const prompts = groundedPrompts(
      {
        obligations: null,
        sources: [source({})],
        projects: [project({ id: 'p1', name: 'Ride Share' }), project({ id: 'p2', name: 'Keyline' })],
        plans: [
          task({ id: 'old', project_id: 'p2', updated_at: NOW - 400_000 }),
          task({ id: 'a', project_id: 'p1', created_at: NOW - 9_000, updated_at: NOW - 7_200 }),
          task({ id: 'b', project_id: 'p1', created_at: NOW - 8_000, updated_at: NOW - 3_600 }),
        ],
      },
      NOW,
    );
    expect(prompts[0]).toEqual({
      prompt: 'What are the unfinished tasks in Ride Share?',
      reason: '2 unfinished tasks · last touched today',
      action: {
        kind: 'continue-tasks',
        projectId: 'p1',
        tasks: [expect.objectContaining({ id: 'a' }), expect.objectContaining({ id: 'b' })],
      },
    });
    // The rest of the list is unchanged, behind it.
    expect(prompts[1].prompt).toBe('What is in Abuja, in a few lines?');
  });

  it('is the project touched last, not the one with the most tasks', () => {
    const prompts = groundedPrompts(
      {
        obligations: null,
        sources: null,
        projects: [project({ id: 'p1', name: 'Ride Share' }), project({ id: 'p2', name: 'Keyline' })],
        plans: [
          task({ id: 'x', project_id: 'p1', updated_at: NOW - 900_000 }),
          task({ id: 'y', project_id: 'p1', updated_at: NOW - 800_000 }),
          task({ id: 'z', project_id: 'p2', updated_at: NOW - 60 }),
        ],
      },
      NOW,
    );
    expect(prompts[0].prompt).toBe('What are the unfinished tasks in Keyline?');
    expect(prompts[0].reason).toBe('1 unfinished task · last touched today');
  });

  it('offers nothing for finished tasks, unread tasks, or a project that is gone', () => {
    const projects = [project({ id: 'p1', name: 'Ride Share', facts: 0 })];
    const none = (plans: UnfinishedTask[] | null | undefined) =>
      groundedPrompts({ obligations: null, sources: null, projects, plans }, NOW);
    expect(none([task({ finished: true })])).toEqual([]);
    expect(none(null)).toEqual([]);
    expect(none(undefined)).toEqual([]);
    // No bare id on the first line: an unknown project contributes no row.
    expect(none([task({ project_id: 'deleted-project' })])).toEqual([]);
    // A task that belongs to no project has no "latest project" to name.
    expect(none([task({ project_id: '' })])).toEqual([]);
  });
});

describe('the thread they were last in comes next', () => {
  const convo = (over: Partial<ConversationSummary>): ConversationSummary => ({
    id: 'c1',
    title: 'pick a stack for a rideshare app',
    projectId: '',
    createdAt: NOW - 90_000,
    updatedAt: NOW - 7_200,
    messageCount: 6,
    pinned: false,
    ...over,
  });
  const ask = (conversations: ConversationSummary[] | null | undefined) =>
    groundedPrompts({ obligations: null, sources: null, projects: [], conversations }, NOW);

  it('names it by its own title and carries the id to reopen', () => {
    expect(ask([convo({})])).toEqual([
      {
        prompt: 'Pick up where you left off: pick a stack for a rideshare app',
        reason: '6 messages · today',
        action: { kind: 'reopen', conversationId: 'c1' },
      },
    ]);
  });

  it('is the one with the latest activity, and never an empty one', () => {
    const rows = ask([
      convo({ id: 'old', updatedAt: NOW - 500_000 }),
      convo({ id: 'empty', updatedAt: NOW - 10, messageCount: 0 }),
      convo({ id: 'recent', updatedAt: NOW - 600 }),
    ]);
    expect(rows[0].action).toEqual({ kind: 'reopen', conversationId: 'recent' });
  });

  it('shortens a title that is a paragraph, and offers nothing when unread or empty', () => {
    const long = 'x'.repeat(200);
    expect(ask([convo({ title: long })])[0].prompt.length).toBeLessThan(80);
    expect(ask([])).toEqual([]);
    expect(ask(null)).toEqual([]);
    expect(ask(undefined)).toEqual([]);
  });

  it('sits after what is unfinished', () => {
    const rows = groundedPrompts(
      {
        obligations: null,
        sources: null,
        projects: [project({ id: 'p1', name: 'Ride Share', facts: 0 })],
        plans: [{ id: 't', project_id: 'p1', finished: false, updated_at: NOW - 60 } as UnfinishedTask],
        conversations: [convo({})],
      },
      NOW,
    );
    expect(rows.map((r) => r.action?.kind)).toEqual(['continue-tasks', 'reopen']);
  });
});
