/**
 * Reopening a conversation gets the work back, not just the words.
 *
 * Reported 3 October 2026: *"when a Zaram session is closed the plans, tools
 * used, files download etc attached to the session seems to disappear."*
 *
 * The measurement that preceded the fix found something worse than the
 * report. Of 50 artifacts in the maintainer's own store, **none** was filed
 * under a conversation that exists — 27 under `''` and 23 under a `session-…`
 * id. The column, its index, the `?conversation_id=` query and the Work
 * surface reading it were all present and correct; the chat path passes the
 * *session* id, minted per launch, where the durable conversation id belongs.
 *
 * Its own file rather than additions to `chatStore.test.ts`, which mocks the
 * chat transport on purpose and is about streaming. This one mocks the two
 * stores a restore reads from and is about what comes back.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const fetchConversation = vi.fn();
const listArtifacts = vi.fn();

vi.mock('@/services/conversationsClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/conversationsClient')>()),
  fetchConversation: (...a: unknown[]) => fetchConversation(...(a as [])),
}));

vi.mock('@/services/artifactsClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/artifactsClient')>()),
  listArtifacts: (...a: unknown[]) => listArtifacts(...(a as [])),
}));

import { useChatStore } from '@/stores/chatStore';

function message(over: Record<string, unknown> = {}) {
  return {
    id: 'm1',
    seq: 1,
    role: 'assistant' as const,
    text: 'Here is the spreadsheet.',
    createdAt: 1,
    model: 'qwen2.5:14b',
    locality: 'local',
    toolCalls: [],
    plan: null,
    artifactIds: [],
    ...over,
  };
}

function stored(messages: ReturnType<typeof message>[]) {
  return {
    id: 'conv_1',
    title: 'the spreadsheet',
    projectId: '',
    createdAt: 1,
    updatedAt: 2,
    messageCount: messages.length,
    pinned: false,
    messages,
  };
}

beforeEach(() => {
  fetchConversation.mockReset().mockResolvedValue(stored([message()]));
  listArtifacts.mockReset().mockResolvedValue({ total: 0, offset: 0, limit: 200, artifacts: [] });
  useChatStore.setState({ messages: [] });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('what a reopened reply carries', () => {
  it('brings back the tool calls', async () => {
    fetchConversation.mockResolvedValue(
      stored([
        message({
          toolCalls: [
            { server: 'code', tool: 'read_lines', verdict: 'allow', reason: '', target: 'a.py', output: '', at: 0 },
          ],
        }),
      ]),
    );
    await useChatStore.getState().resumeConversation('conv_1');
    expect(useChatStore.getState().messages[0].toolCalls?.[0].tool).toBe('read_lines');
  });

  it('brings back the checklist', async () => {
    fetchConversation.mockResolvedValue(
      stored([message({ plan: { items: [{ text: 'read the figures', status: 'done' }], awaitingGo: false } })]),
    );
    await useChatStore.getState().resumeConversation('conv_1');
    expect(useChatStore.getState().messages[0].plan?.items[0].text).toBe('read the figures');
  });

  it('brings back the files it made', async () => {
    fetchConversation.mockResolvedValue(stored([message({ artifactIds: ['art_1'] })]));
    listArtifacts.mockResolvedValue({
      total: 1,
      offset: 0,
      limit: 200,
      artifacts: [{ id: 'art_1', filename: 'q3.xlsx' }],
    });
    await useChatStore.getState().resumeConversation('conv_1');
    expect(useChatStore.getState().messages[0].artifacts[0].filename).toBe('q3.xlsx');
  });

  it('asks the artifact store for this conversation and no other', async () => {
    fetchConversation.mockResolvedValue(stored([message({ artifactIds: ['art_1'] })]));
    await useChatStore.getState().resumeConversation('conv_1');
    expect(listArtifacts).toHaveBeenCalledWith({ conversationId: 'conv_1' });
  });

  it('drops an id whose file has since gone', async () => {
    // Rule 4 and the trash both outlive the transcript. A card for a file
    // that is not there is the "file not found" the live card already
    // refuses to render.
    fetchConversation.mockResolvedValue(stored([message({ artifactIds: ['art_1', 'gone'] })]));
    listArtifacts.mockResolvedValue({
      total: 1,
      offset: 0,
      limit: 200,
      artifacts: [{ id: 'art_1', filename: 'q3.xlsx' }],
    });
    await useChatStore.getState().resumeConversation('conv_1');
    expect(useChatStore.getState().messages[0].artifacts).toHaveLength(1);
  });

  it('opens the transcript even when the artifact store does not answer', async () => {
    // Losing the file cards is a smaller failure than refusing to show
    // somebody their conversation.
    fetchConversation.mockResolvedValue(stored([message({ artifactIds: ['art_1'] })]));
    listArtifacts.mockRejectedValue(new Error('backend down'));
    await useChatStore.getState().resumeConversation('conv_1');
    expect(useChatStore.getState().messages[0].text).toBe('Here is the spreadsheet.');
    expect(useChatStore.getState().messages[0].artifacts).toEqual([]);
  });

  it('leaves a plain reply without a plan or a tool list', async () => {
    await useChatStore.getState().resumeConversation('conv_1');
    const restored = useChatStore.getState().messages[0];
    expect(restored.plan).toBeUndefined();
    expect(restored.toolCalls).toBeUndefined();
  });
});

describe('what it still refuses to restore', () => {
  /** A citation is a live claim that *this* answer used *that* fact, and rule
   *  4 lets the fact be corrected or deleted. Yesterday's citation rendered
   *  against today's Spine shows provenance that no longer holds — worse than
   *  showing none.
   *
   *  The fix above deliberately stops short of this line: a tool call, a
   *  checklist and a file are records of what happened and cannot go stale. */
  it('does not invent sources for a restored reply', async () => {
    fetchConversation.mockResolvedValue(
      stored([message({ toolCalls: [{ server: 's', tool: 't', verdict: 'allow', reason: '', target: '', output: '', at: 0 }] })]),
    );
    await useChatStore.getState().resumeConversation('conv_1');
    expect(useChatStore.getState().messages[0].sources).toEqual([]);
  });
});

describe('the project follows the conversation', () => {
  /** Rule 7i. Opening a Keyline conversation while Ride Share is selected
   *  leaves the next question scoped to Ride Share, so facts captured from it
   *  land under a project the exchange is not about. */
  it('switches to the project the conversation belongs to', async () => {
    useChatStore.setState({ projectId: 'ride-share' });
    fetchConversation.mockResolvedValue({ ...stored([message()]), projectId: 'keyline' });
    await useChatStore.getState().resumeConversation('conv_1');
    expect(useChatStore.getState().projectId).toBe('keyline');
  });

  it('clears the project when the conversation belongs to none', async () => {
    // The same fault pointing the other way: continuing an unscoped thread
    // with a project selected captures its facts under that project.
    useChatStore.setState({ projectId: 'ride-share' });
    fetchConversation.mockResolvedValue({ ...stored([message()]), projectId: '' });
    await useChatStore.getState().resumeConversation('conv_1');
    expect(useChatStore.getState().projectId).toBeNull();
  });

  it('remembers the switch across a relaunch', async () => {
    fetchConversation.mockResolvedValue({ ...stored([message()]), projectId: 'keyline' });
    await useChatStore.getState().resumeConversation('conv_1');
    expect(localStorage.getItem('zaram.activeProject')).toBe('keyline');
  });

  it('and forgets it when the conversation had none', async () => {
    localStorage.setItem('zaram.activeProject', 'ride-share');
    fetchConversation.mockResolvedValue({ ...stored([message()]), projectId: '' });
    await useChatStore.getState().resumeConversation('conv_1');
    expect(localStorage.getItem('zaram.activeProject')).toBeNull();
  });
});
