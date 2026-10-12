/**
 * @vitest-environment jsdom
 *
 * An app Zaram starts in a conversation opens in its own pane -- once, and only
 * when it happened just now.
 *
 * 11 October 2026, the maintainer: *"instead of just giving the user a link to
 * the localhost and telling the user to open it in the browser, it actually
 * opens the localhost."* The guards (local address, the code pack's own tools,
 * waiting for an answer) are in `lib/openStartedApp.test.ts`; this file is the
 * wiring: that the live stream reaches it, once per call, and that a
 * conversation read back from history does not.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ChatEvent } from '@/services/chatClient';

const streamChat = vi.fn();
const fetchConversation = vi.fn();
const openStartedApp = vi.fn(async () => true);

vi.mock('@/services/chatClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/chatClient')>()),
  streamChat: (...args: unknown[]) => streamChat(...args),
}));
vi.mock('@/services/conversationsClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/conversationsClient')>()),
  fetchConversation: (...a: unknown[]) => fetchConversation(...(a as [])),
}));
vi.mock('@/services/artifactsClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/artifactsClient')>()),
  listArtifacts: async () => ({ total: 0, offset: 0, limit: 200, artifacts: [] }),
}));
vi.mock('@/lib/openStartedApp', () => ({
  openStartedApp: (...a: unknown[]) => (openStartedApp as (...x: unknown[]) => unknown)(...a),
}));

import { useChatStore } from '@/stores/chatStore';

function finished(events: ChatEvent[]) {
  return () =>
    (async function* () {
      for (const e of events) yield e;
    })();
}

function started(tool: string, appUrl: string, verdict = 'allow'): ChatEvent {
  return {
    type: 'tool_call',
    server: 'code',
    tool,
    verdict,
    reason: '',
    target: '',
    output: '',
    diff: '',
    commit: '',
    image: '',
    appUrl,
  } as ChatEvent;
}

beforeEach(() => {
  streamChat.mockReset();
  openStartedApp.mockClear();
  fetchConversation.mockReset();
  useChatStore.setState({ messages: [], isStreaming: false, streamingText: '' });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('an app the reply started', () => {
  it('is handed on once, with the address the tool reported', async () => {
    streamChat.mockImplementationOnce(finished([started('start_app_stack', 'http://127.0.0.1:5173')]));
    await useChatStore.getState().send('run it');
    expect(openStartedApp).toHaveBeenCalledTimes(1);
    expect(openStartedApp).toHaveBeenCalledWith(
      expect.objectContaining({ server: 'code', tool: 'start_app_stack', verdict: 'allow', appUrl: 'http://127.0.0.1:5173' }),
    );
  });

  it('is handed on as it is, so the guards can decide -- a refused call arrives as a refusal', async () => {
    streamChat.mockImplementationOnce(finished([started('start_app', '', 'refuse')]));
    await useChatStore.getState().send('run it');
    expect(openStartedApp).toHaveBeenCalledWith(expect.objectContaining({ verdict: 'refuse', appUrl: '' }));
  });
});

describe('a conversation reopened from history', () => {
  it('does not open the apps it once started', async () => {
    fetchConversation.mockResolvedValue({
      id: 'conv_1',
      title: 'a site',
      projectId: '',
      createdAt: 1,
      updatedAt: 2,
      messageCount: 1,
      pinned: false,
      messages: [
        {
          id: 'a1',
          seq: 1,
          role: 'assistant',
          text: 'It is running.',
          createdAt: 1,
          model: 'm',
          locality: 'local',
          toolCalls: [
            { server: 'code', tool: 'start_app', verdict: 'allow', reason: 'ran', target: 'dev', output: '', appUrl: 'http://127.0.0.1:5173' },
          ],
          plan: null,
          artifactIds: [],
          sources: [],
        },
      ],
    });
    await useChatStore.getState().resumeConversation('conv_1');
    expect(useChatStore.getState().messages[0].toolCalls?.[0].appUrl).toBe('http://127.0.0.1:5173');
    expect(openStartedApp).not.toHaveBeenCalled();
  });
});
