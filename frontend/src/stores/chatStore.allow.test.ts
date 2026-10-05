/**
 * @vitest-environment jsdom
 *
 * Pressing Allow while the reply is still being written.
 *
 * Reported 5 October 2026: *"when the pop up came to run a terminal I clicked
 * it and still this message — it seems like it happens every time."* Nothing
 * waits on a timer. The permission card appears the moment the gate holds a
 * call, and the reply goes on to answer without the tool, which takes as long
 * as any other reply. `send` returns at once while a reply is streaming, so an
 * Allow pressed in that window saved the grant and then asked nothing: the
 * screen kept the refusal.
 *
 * What has to hold:
 *
 * * **The question is asked again even though a reply is in flight**, with
 *   everything else about the request unchanged.
 * * **The unfinished refusal is discarded**, not left in the transcript beside
 *   its replacement, and the question is not shown twice.
 * * **With nothing in flight it still asks** — the original behaviour, and
 *   what a replayed history needs.
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

/** Yields its events, then waits to be aborted, as a reply still being written does. */
function unfinished(events: ChatEvent[]) {
  return (_req: unknown, signal: AbortSignal) =>
    (async function* () {
      for (const e of events) yield e;
      await new Promise<void>((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
      });
    })();
}

function finished(events: ChatEvent[]) {
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
    conversationId: 'conv_1',
    projectId: 'ride-share',
    domainIds: [],
  });
});

describe('allowing a held tool', () => {
  it('asks again while the refusal is still streaming', async () => {
    streamChat.mockImplementationOnce(unfinished([token('`run_in_terminal` needs your say-so. ')]));
    const first = useChatStore.getState().send('pick a stack for a rideshare app');
    await vi.waitFor(() => expect(useChatStore.getState().streamingText).not.toBe(''));

    streamChat.mockImplementationOnce(finished([token('Ran it.')]));
    await useChatStore.getState().askAgainAfterAllowing();
    await first;

    expect(streamChat).toHaveBeenCalledTimes(2);
    const again = streamChat.mock.calls[1][0];
    expect(again.text).toBe('pick a stack for a rideshare app');
    expect(again.conversationId).toBe('conv_1');
    expect(again.projectId).toBe('ride-share');
  });

  it('leaves one question and one answer, not the refusal beside its replacement', async () => {
    streamChat.mockImplementationOnce(unfinished([token('I cannot run that. ')]));
    const first = useChatStore.getState().send('set it up');
    await vi.waitFor(() => expect(useChatStore.getState().streamingText).not.toBe(''));

    streamChat.mockImplementationOnce(finished([token('Done.')]));
    await useChatStore.getState().askAgainAfterAllowing();
    await first;

    const { messages, isStreaming } = useChatStore.getState();
    expect(isStreaming).toBe(false);
    expect(messages.filter((m) => m.role === 'user')).toHaveLength(1);
    const answers = messages.filter((m) => m.role === 'assistant');
    expect(answers).toHaveLength(1);
    expect(answers[0].text).toBe('Done.');
  });

  it('asks again when nothing is in flight', async () => {
    streamChat.mockImplementationOnce(finished([token('I cannot run that.')]));
    await useChatStore.getState().send('set it up');
    expect(streamChat).toHaveBeenCalledTimes(1);

    streamChat.mockImplementationOnce(finished([token('Done.')]));
    await useChatStore.getState().askAgainAfterAllowing();

    expect(streamChat).toHaveBeenCalledTimes(2);
    expect(streamChat.mock.calls[1][0].text).toBe('set it up');
  });
});

describe('carrying a parked task on', () => {
  it('runs the held call once, keeping the question on screen', async () => {
    streamChat.mockImplementationOnce(finished([token('`run_in_terminal` needs your say-so.')]));
    await useChatStore.getState().send('set up the project');

    streamChat.mockImplementationOnce(finished([token('Installed.')]));
    await useChatStore.getState().askAgainAfterAllowing({ planId: 'plan-7', runHeld: true });

    const req = streamChat.mock.calls[1][0];
    expect(req.continueTask).toBe(true);
    expect(req.planId).toBe('plan-7');
    expect(req.runHeld).toBe(true);
    expect(req.text).toBe('Run it once');
    const asked = useChatStore.getState().messages.filter((m) => m.role === 'user').map((m) => m.text);
    expect(asked).toEqual(['set up the project', 'Run it once']);
  });

  it('after a grant, continues without confirming anything', async () => {
    streamChat.mockImplementationOnce(finished([token('needs your say-so.')]));
    await useChatStore.getState().send('set up the project');

    streamChat.mockImplementationOnce(finished([token('Done.')]));
    await useChatStore.getState().askAgainAfterAllowing({ planId: 'plan-7', runHeld: false });

    const req = streamChat.mock.calls[1][0];
    expect(req.continueTask).toBe(true);
    expect(req.runHeld).toBeUndefined();
    expect(req.text).toBe('Continue');
  });
});

describe('the recall row carries the facts', () => {
  it('puts what was recalled in the row’s output, so opening it shows them', async () => {
    streamChat.mockImplementationOnce(
      finished([
        {
          type: 'step_complete',
          stepId: 'recall',
          capability: 'memory.recall',
          success: true,
          done: 'Recalled 2 facts',
          target: '',
          detail: '',
          seconds: null,
          output: '0.53  a conversation · The launch is in Bristol.\n0.48  your document · Terms: 30 days.',
        } as ChatEvent,
        token('Answer.'),
      ]),
    );
    await useChatStore.getState().send('when is the launch');

    const reply = useChatStore.getState().messages.find((m) => m.role === 'assistant');
    const row = reply?.toolCalls?.find((c) => c.stepId === 'recall');
    expect(row?.label).toBe('Recalled 2 facts');
    expect(row?.output).toContain('The launch is in Bristol.');
  });
});
