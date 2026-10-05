/**
 * @vitest-environment jsdom
 *
 * Continuing every unfinished task in a project, one after another.
 *
 * The row that offers waiting work used to resume only the newest task and
 * leave the others for Project to find. `runInOrder` is what lets one press
 * carry them all, and the property that makes it safe is where it *stops*: a
 * task that ends waiting on the person -- a plan held for Go, a permission
 * card, an error -- or a Stop press must not be followed by the next task,
 * because that would proceed under a decision nobody has made.
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

const token = (content: string): ChatEvent => ({ type: 'token', content }) as ChatEvent;
const plan = (awaitingGo: boolean): ChatEvent =>
  ({ type: 'plan', items: [{ text: 'step one', status: 'todo' }], awaitingGo }) as ChatEvent;

function finished(events: ChatEvent[]) {
  return (_req: unknown, _signal: AbortSignal) =>
    (async function* () {
      for (const e of events) yield e;
    })();
}

const steps = [
  { text: 'What are the unfinished tasks in Ride Share?', opts: { continueTask: true, planId: 'old' } },
  { text: 'Continue', opts: { continueTask: true, planId: 'new' } },
];

beforeEach(() => {
  streamChat.mockReset();
  useSystemStore.setState({ activity: 'idle', swappingTo: null, oversizedModel: null });
  useChatStore.setState({
    messages: [],
    isStreaming: false,
    streamingText: '',
    connectionError: null,
    conversationId: 'conv_1',
    projectId: 'ride-share',
    domainIds: [],
  });
});

describe('running tasks in order', () => {
  it('sends each when the last has ended, naming the task each time', async () => {
    streamChat
      .mockImplementationOnce(finished([plan(false), token('first done')]))
      .mockImplementationOnce(finished([token('second done')]));

    await useChatStore.getState().runInOrder(steps);

    expect(streamChat).toHaveBeenCalledTimes(2);
    expect(streamChat.mock.calls.map((c) => [c[0].continueTask, c[0].planId])).toEqual([
      [true, 'old'],
      [true, 'new'],
    ]);
    expect(streamChat.mock.calls[0][0].projectId).toBe('ride-share');
  });

  it('stops where a plan is held for Go, because the next task is not the person’s answer', async () => {
    streamChat.mockImplementationOnce(finished([plan(true), token('Here is the plan.')]));

    await useChatStore.getState().runInOrder(steps);

    expect(streamChat).toHaveBeenCalledTimes(1);
  });

  it('stops where a permission card is waiting', async () => {
    streamChat.mockImplementationOnce(
      finished([
        {
          type: 'tool_call',
          server: 'code',
          tool: 'run_in_terminal',
          verdict: 'confirm',
          reason: 'needs your say-so',
          target: '',
          grantable: true,
          grantScope: 'shell',
        } as unknown as ChatEvent,
        token('I could not run it.'),
      ]),
    );

    await useChatStore.getState().runInOrder(steps);

    expect(streamChat).toHaveBeenCalledTimes(1);
  });

  it('stops when the person presses Stop', async () => {
    streamChat.mockImplementationOnce(
      (_req: unknown, signal: AbortSignal) =>
        (async function* () {
          yield token('working… ');
          await new Promise<void>((_resolve, reject) => {
            signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
          });
        })(),
    );

    const run = useChatStore.getState().runInOrder(steps);
    await vi.waitFor(() => expect(useChatStore.getState().streamingText).not.toBe(''));
    useChatStore.getState().cancel();
    await run;

    expect(streamChat).toHaveBeenCalledTimes(1);
  });
});
