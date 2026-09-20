/**
 * @vitest-environment jsdom
 *
 * What the orb says while a reply is on its way.
 *
 * **"Warming up" on every question has now been reported twice**, and the two
 * reports were different bugs with one label. The first was residency: the
 * backend could not tell whether the model was loaded, so it said nothing, and
 * this store's 2.5-second timer — which exists to guess that silence means a
 * cold model — fired on a model that had not moved. The second is here: a
 * reply routed to a *cloud* model has no local model to warm at all, and the
 * label said "Starting the local model" under a request that had left the
 * machine. Measured 3 September 2026 against a model reached through
 * OpenRouter.
 *
 * Nothing tested this store's streaming at all, which is why a guess about
 * local loading could sit on the cloud path for as long as it did. Fake timers
 * rather than real waiting: the whole contract is *when* the guess fires and
 * *what cancels it*, and a test that slept for it would be slow and flaky
 * about the one thing it is asserting.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ChatEvent } from '@/services/chatClient';

const streamChat = vi.fn();

vi.mock('@/services/chatClient', () => ({
  streamChat: (...args: unknown[]) => streamChat(...args),
}));

import { useChatStore } from '@/stores/chatStore';
import { useSystemStore } from '@/stores/systemStore';

/** A stream that yields `events`, then waits to be released before ending.
 *
 *  The pause is the point: it is the silence the timer measures, and a
 *  generator that returned straight away would settle the activity before the
 *  guess could ever fire. */
function pausedStream(events: ChatEvent[]) {
  let release: () => void = () => {};
  const finished = new Promise<void>((resolve) => {
    release = resolve;
  });

  async function* stream() {
    for (const event of events) yield event;
    await finished;
  }

  return { stream, release };
}

describe('the wait, while a reply is on its way', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    streamChat.mockReset();
    useSystemStore.setState({ activity: 'idle', swappingTo: null, oversizedModel: null });
    useChatStore.setState({ messages: [], isStreaming: false, streamingText: '' });
  });

  it('guesses a cold local model when nothing has said otherwise', async () => {
    const { stream, release } = pausedStream([]);
    streamChat.mockImplementation(() => stream());

    const sending = useChatStore.getState().send('what is a deposit clause?');
    await vi.advanceTimersByTimeAsync(2600);

    expect(useSystemStore.getState().activity).toBe('warming');

    release();
    await sending;
  });

  it('does not, once a cloud model says it is the one answering', async () => {
    const { stream, release } = pausedStream([
      {
        type: 'answering',
        model: 'meta/llama-spark-1.3',
        locality: 'cloud',
        provider: 'openrouter',
        chosenBy: 'message',
      },
    ]);
    streamChat.mockImplementation(() => stream());

    const sending = useChatStore.getState().send('what is a deposit clause?');
    await vi.advanceTimersByTimeAsync(2600);

    expect(useSystemStore.getState().activity).toBe('thinking');

    release();
    await sending;
  });

  it('still guesses when the backend could not place the model', async () => {
    // `null` locality is the backend saying it could not resolve where the
    // model runs. A guess either way would be a claim about whether this
    // person's question left their machine, so the wait is named the way every
    // other unresolved wait is and the label is left to the timer.
    const { stream, release } = pausedStream([
      {
        type: 'answering',
        model: 'something-unresolved',
        locality: null,
        provider: null,
        chosenBy: null,
      },
    ]);
    streamChat.mockImplementation(() => stream());

    const sending = useChatStore.getState().send('what is a deposit clause?');
    await vi.advanceTimersByTimeAsync(2600);

    expect(useSystemStore.getState().activity).toBe('warming');

    release();
    await sending;
  });

  it('stops guessing the moment the backend says the model is resident', async () => {
    // The other half of the same rule, and the one the 31 August session fixed
    // three layers of. Kept here because those three layers are now correct
    // and nothing above them asserted the outcome.
    const { stream, release } = pausedStream([
      { type: 'model_load', kind: 'resident', model: 'qwen3-14b-8k', evicts: [] },
    ]);
    streamChat.mockImplementation(() => stream());

    const sending = useChatStore.getState().send('what is a deposit clause?');
    await vi.advanceTimersByTimeAsync(2600);

    expect(useSystemStore.getState().activity).toBe('thinking');

    release();
    await sending;
  });
});

describe('a file sent with a question', () => {
  // Raised by the maintainer, 13 September: after send the file should sit on
  // the question it went with, not stay in the composer bar. The message is
  // where the record lives; the ids still travel with the request.
  it('is recorded on the user message and sent by id', async () => {
    const { stream, release } = pausedStream([]);
    streamChat.mockImplementation(() => stream());

    const sending = useChatStore
      .getState()
      .send('what does clause 4 say?', { attachmentIds: ['att-1'] }, [
        { id: 'att-1', name: 'lease.pdf', kind: 'document' },
      ]);
    const asked = [...useChatStore.getState().messages].reverse().find((m) => m.role === 'user');
    expect(asked?.attachments).toEqual([{ id: 'att-1', name: 'lease.pdf', kind: 'document' }]);
    expect(streamChat.mock.calls[streamChat.mock.calls.length - 1]?.[0]).toMatchObject({ attachmentIds: ['att-1'] });

    release();
    await sending;
  });

  it('is absent, not empty, on a question sent without one', async () => {
    const { stream, release } = pausedStream([]);
    streamChat.mockImplementation(() => stream());
    const sending = useChatStore.getState().send('and clause 5?');
    const asked = [...useChatStore.getState().messages].reverse().find((m) => m.role === 'user');
    expect(asked).toBeDefined();
    expect('attachments' in (asked ?? {})).toBe(false);
    release();
    await sending;
  });
});

describe('the open-project offer keeps what makes it pressable', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    streamChat.mockReset();
    useSystemStore.setState({ activity: 'idle', swappingTo: null, oversizedModel: null });
    useChatStore.setState({ messages: [], isStreaming: false, streamingText: '' });
  });

  // Seen 20 September 2026, the first time F1 ran on screen: the card asked
  // "Open it as a coding project?" with nothing to press. `chatClient` parsed
  // `path` and `name`; this store dropped them; `NoticeCard` offers the
  // button only when `path` is there. A test that hands the card a complete
  // notice cannot see that.
  it('carries path and name from the event onto the stored notice', async () => {
    const { stream, release } = pausedStream([
      {
        type: 'notice',
        content: 'That names a folder on this machine — C:/code/my-app. Open it as a coding project?',
        kind: 'project',
        action: 'open-project',
        path: 'C:/code/my-app',
        name: 'my-app',
      },
    ]);
    streamChat.mockImplementation(() => stream());

    const sending = useChatStore.getState().send('have a look at C:/code/my-app');
    await vi.advanceTimersByTimeAsync(10);
    expect(useChatStore.getState().streamingNotices[0]).toMatchObject({
      action: 'open-project',
      path: 'C:/code/my-app',
      name: 'my-app',
    });

    release();
    await sending;
    const reply = [...useChatStore.getState().messages].reverse().find((m) => m.role === 'assistant');
    expect(reply?.notices[0]).toMatchObject({ path: 'C:/code/my-app', name: 'my-app' });
  });
});
