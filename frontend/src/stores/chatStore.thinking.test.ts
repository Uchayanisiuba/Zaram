/**
 * @vitest-environment jsdom
 *
 * Giving up on thinking, for one message.
 *
 * Measured 4 October 2026: a looping CSS animation took 870 s on the resident
 * 27B, 87% of it reasoning. "Answer without thinking" abandons the attempt and
 * asks the same question again with thinking off. The properties that make that
 * safe, because it is an abort followed by a send and the two overlap in time:
 *
 * * **The retry is the same question, exactly** — same text, with the override
 *   and the retry flag, and nothing else about the request changed.
 * * **The question is not shown twice**, and earlier turns are untouched.
 * * **The abandoned attempt commits nothing.** Its cleanup runs after the retry
 *   has started; a reasoning-only message in the transcript, or the orb flipped
 *   to idle under the new request, is the race this exists to prevent.
 * * **It does nothing when nothing is thinking.**
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ChatEvent } from '@/services/chatClient';

const streamChat = vi.fn();

vi.mock('@/services/chatClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/chatClient')>()),
  streamChat: (...args: unknown[]) => streamChat(...args),
}));

import { useChatStore } from '@/stores/chatStore';
import { useSystemStore } from '@/stores/systemStore';

const reasoning = (content: string): ChatEvent => ({ type: 'reasoning', content }) as ChatEvent;
const token = (content: string): ChatEvent => ({ type: 'token', content }) as ChatEvent;

/** A stream that yields its events and then waits to be told to end, or to be
 *  aborted — which throws the way a real fetch does. */
function hangingStream(events: ChatEvent[]) {
  return (_req: unknown, signal: AbortSignal) =>
    (async function* () {
      for (const e of events) yield e;
      await new Promise<void>((resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
        void resolve;
      });
    })();
}

function finishedStream(events: ChatEvent[]) {
  return (_req: unknown, _signal: AbortSignal) =>
    (async function* () {
      for (const e of events) yield e;
    })();
}

beforeEach(() => {
  streamChat.mockReset();
  useSystemStore.setState({ activity: 'idle', swappingTo: null, oversizedModel: null });
  useChatStore.setState({
    messages: [],
    isStreaming: false,
    streamingText: '',
    streamingReasoning: '',
    streamingReasoningSince: null,
    conversationId: 'conv_1',
    projectId: 'keyline',
    domainIds: [],
  });
});

async function startThinking(text = 'a bouncing ball') {
  streamChat.mockImplementationOnce(hangingStream([reasoning('hmm, a ball… ')]));
  const first = useChatStore.getState().send(text);
  await vi.waitFor(() => expect(useChatStore.getState().streamingReasoning).not.toBe(''));
  // Wrapped: an async function that returns a promise *adopts* it, so returning
  // `first` bare made every `await startThinking()` wait for the send to finish
  // — which it cannot, while it is hanging on purpose.
  return { first };
}

describe('the clock', () => {
  it('starts when the first reasoning arrives and not before', async () => {
    streamChat.mockImplementationOnce(hangingStream([]));
    const first = useChatStore.getState().send('hi');
    await vi.waitFor(() => expect(useChatStore.getState().isStreaming).toBe(true));
    expect(useChatStore.getState().streamingReasoningSince).toBeNull();
    useChatStore.getState().cancel();
    await first;
  });

  it('is set once thinking begins', async () => {
    const { first } = await startThinking();
    expect(useChatStore.getState().streamingReasoningSince).toBeGreaterThan(0);
    useChatStore.getState().cancel();
    await first;
  });
});

describe('answering without thinking', () => {
  it('asks the same question again with thinking off and the retry flag', async () => {
    const { first } = await startThinking('a bouncing ball');
    streamChat.mockImplementationOnce(finishedStream([token('Here it is.')]));

    await useChatStore.getState().answerWithoutThinking();
    await first;

    expect(streamChat).toHaveBeenCalledTimes(2);
    const retry = streamChat.mock.calls[1][0];
    expect(retry.text).toBe('a bouncing ball');
    expect(retry.thinking).toBe(false);
    expect(retry.retry).toBe(true);
    // Nothing else about the request moved.
    expect(retry.conversationId).toBe('conv_1');
    expect(retry.projectId).toBe('keyline');
  });

  it('leaves the first attempt without an override', async () => {
    const { first } = await startThinking();
    streamChat.mockImplementationOnce(finishedStream([token('ok')]));
    await useChatStore.getState().answerWithoutThinking();
    await first;
    expect(streamChat.mock.calls[0][0].thinking).toBeUndefined();
    expect(streamChat.mock.calls[0][0].retry).toBeUndefined();
  });

  it('shows the question once and the answer once', async () => {
    const { first } = await startThinking('a bouncing ball');
    streamChat.mockImplementationOnce(finishedStream([token('Here it is.')]));
    await useChatStore.getState().answerWithoutThinking();
    await first;

    const messages = useChatStore.getState().messages;
    expect(messages.map((m) => [m.role, m.text])).toEqual([
      ['user', 'a bouncing ball'],
      ['assistant', 'Here it is.'],
    ]);
  });

  it('commits nothing made of the abandoned reasoning', async () => {
    const { first } = await startThinking();
    streamChat.mockImplementationOnce(finishedStream([token('ok')]));
    await useChatStore.getState().answerWithoutThinking();
    await first;

    const assistant = useChatStore.getState().messages.filter((m) => m.role === 'assistant');
    expect(assistant).toHaveLength(1);
    expect(assistant[0].reasoning).toBeUndefined();
  });

  it('does not touch earlier turns', async () => {
    useChatStore.setState({
      messages: [
        { id: 'a', role: 'user', text: 'earlier', sources: [], artifacts: [], notices: [], timestamp: 1 },
        { id: 'b', role: 'assistant', text: 'earlier answer', sources: [], artifacts: [], notices: [], timestamp: 2 },
      ],
    });
    const { first } = await startThinking('a bouncing ball');
    streamChat.mockImplementationOnce(finishedStream([token('ok')]));
    await useChatStore.getState().answerWithoutThinking();
    await first;

    expect(useChatStore.getState().messages.map((m) => m.text)).toEqual([
      'earlier', 'earlier answer', 'a bouncing ball', 'ok',
    ]);
  });

  it('does not let the abandoned attempt flip the activity under the new request', async () => {
    const { first } = await startThinking();
    // The retry hangs, so the store is mid-request when the old one cleans up.
    streamChat.mockImplementationOnce(hangingStream([token('partial')]));
    const retried = useChatStore.getState().answerWithoutThinking();
    await first; // the abandoned attempt has finished its cleanup

    expect(useChatStore.getState().isStreaming).toBe(true);
    expect(useSystemStore.getState().activity).not.toBe('idle');

    useChatStore.getState().cancel();
    await retried;
  });

  it('does nothing when no reply is in flight', async () => {
    await useChatStore.getState().answerWithoutThinking();
    expect(streamChat).not.toHaveBeenCalled();
  });

  it('does nothing before anything was ever sent', async () => {
    useChatStore.setState({ isStreaming: true });
    await useChatStore.getState().answerWithoutThinking();
    // `isStreaming` with no controller in flight is not a reply to abandon.
    expect(streamChat).not.toHaveBeenCalled();
    useChatStore.setState({ isStreaming: false });
  });
});
