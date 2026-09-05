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
