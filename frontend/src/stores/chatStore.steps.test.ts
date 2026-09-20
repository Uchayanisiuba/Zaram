/**
 * A plan step is one row that settles in place — never two.
 *
 * `step_start` arrives before the step runs and `step_complete` after; both
 * carry the same `stepId`, and the store must update the row it already has
 * rather than append a second. Recall reports only a completion and stands
 * as a row of its own. A step the backend sent with no words gets no row.
 * `docs/PLAN.md` B1.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ChatEvent } from '@/services/chatClient';

const streamChat = vi.fn();

vi.mock('@/services/chatClient', () => ({
  streamChat: (...args: unknown[]) => streamChat(...args),
}));

import { useChatStore } from '@/stores/chatStore';

async function* events(list: ChatEvent[]) {
  for (const event of list) yield event;
}

describe('step rows', () => {
  beforeEach(() => {
    streamChat.mockReset();
    useChatStore.setState({ messages: [], isStreaming: false, streamingText: '', streamingToolCalls: [] });
  });

  it('starts a running row and settles the same row on completion', async () => {
    streamChat.mockImplementation(() =>
      events([
        { type: 'step_start', stepId: 's1', capability: 'knowledge.search', doing: 'Searching the web', done: 'Searched the web', target: 'fable outage' },
        { type: 'step_complete', stepId: 's1', capability: 'knowledge.search', success: true, done: 'Searched the web', target: 'fable outage', detail: '4 results', seconds: 1.2 },
        { type: 'token', content: 'Here is what happened.' },
        { type: 'done' },
      ]),
    );

    await useChatStore.getState().send('what happened');

    const last = useChatStore.getState().messages[useChatStore.getState().messages.length - 1];
    expect(last?.toolCalls).toHaveLength(1);
    expect(last?.toolCalls?.[0]).toMatchObject({
      server: 'zaram',
      tool: 'knowledge.search',
      verdict: 'allow',
      label: 'Searched the web',
      target: 'fable outage',
      reason: '4 results',
      seconds: 1.2,
    });
  });

  it('is running between the two events', async () => {
    let seen: unknown = null;
    streamChat.mockImplementation(() =>
      (async function* () {
        yield { type: 'step_start', stepId: 's1', capability: 'knowledge.search', doing: 'Searching the web', done: 'Searched the web', target: 'q' } as ChatEvent;
        seen = useChatStore.getState().streamingToolCalls[0];
        yield { type: 'done' } as ChatEvent;
      })(),
    );

    await useChatStore.getState().send('q');

    expect(seen).toMatchObject({ verdict: 'running', doing: 'Searching the web' });
  });

  it('a failed step is a refused row carrying what went wrong', async () => {
    streamChat.mockImplementation(() =>
      events([
        { type: 'step_start', stepId: 's1', capability: 'knowledge.search', doing: 'Searching the web', done: 'Searched the web', target: 'q' },
        { type: 'step_complete', stepId: 's1', capability: 'knowledge.search', success: false, done: 'Searched the web', target: 'q', detail: 'search is off', seconds: 0.1 },
        { type: 'token', content: 'answer' },
        { type: 'done' },
      ]),
    );
    await useChatStore.getState().send('q');
    expect(useChatStore.getState().messages[useChatStore.getState().messages.length - 1]?.toolCalls?.[0]).toMatchObject({
      verdict: 'refuse',
      reason: 'search is off',
    });
  });

  it('recall, which reports only a completion, is a row of its own', async () => {
    streamChat.mockImplementation(() =>
      events([
        { type: 'step_complete', stepId: 'recall', capability: 'memory.recall', success: true, done: 'Recalled 3 facts', target: '', detail: '', seconds: null },
        { type: 'token', content: 'answer' },
        { type: 'done' },
      ]),
    );
    await useChatStore.getState().send('q');
    expect(useChatStore.getState().messages[useChatStore.getState().messages.length - 1]?.toolCalls).toEqual([
      expect.objectContaining({ verdict: 'allow', label: 'Recalled 3 facts', tool: 'memory.recall' }),
    ]);
  });

  it('a step the backend sent without words gets no row', async () => {
    streamChat.mockImplementation(() =>
      events([
        { type: 'step_start', stepId: 's9', capability: 'mcp.list_tools', doing: '', done: '', target: '' },
        { type: 'step_complete', stepId: 's9', capability: 'mcp.list_tools', success: true, done: '', target: '', detail: '', seconds: 0 },
        { type: 'token', content: 'answer' },
        { type: 'done' },
      ]),
    );
    await useChatStore.getState().send('q');
    expect(useChatStore.getState().messages[useChatStore.getState().messages.length - 1]?.toolCalls).toBeUndefined();
  });
});

describe("the engine's own checklist is live-only", () => {
  beforeEach(() => {
    streamChat.mockReset();
    useChatStore.setState({ messages: [], isStreaming: false, streamingText: '', streamingToolCalls: [], streamingPlan: null });
  });

  it('shows while the reply is in flight and is not kept on the message', async () => {
    let live: unknown = null;
    streamChat.mockImplementation(() =>
      (async function* () {
        yield { type: 'plan', items: [{ text: 'Searching the web', status: 'doing' }, { text: 'Answering', status: 'todo' }], awaitingGo: false, source: 'planner' } as ChatEvent;
        live = useChatStore.getState().streamingPlan;
        yield { type: 'token', content: 'answer' } as ChatEvent;
        yield { type: 'done' } as ChatEvent;
      })(),
    );
    await useChatStore.getState().send('q');
    expect(live).toMatchObject({ items: [{ text: 'Searching the web', status: 'doing' }, { text: 'Answering' }] });
    const last = useChatStore.getState().messages[useChatStore.getState().messages.length - 1];
    expect(last?.plan).toBeUndefined();
  });

  it("the model's own checklist still stays on the message", async () => {
    streamChat.mockImplementation(() =>
      events([
        { type: 'plan', items: [{ text: 'Read the store', status: 'done' }], awaitingGo: false },
        { type: 'token', content: 'answer' },
        { type: 'done' },
      ]),
    );
    await useChatStore.getState().send('q');
    const last = useChatStore.getState().messages[useChatStore.getState().messages.length - 1];
    expect(last?.plan?.items).toEqual([{ text: 'Read the store', status: 'done' }]);
  });
});
