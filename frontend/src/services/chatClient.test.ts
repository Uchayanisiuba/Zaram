/**
 * @vitest-environment node
 *
 * Transport tests — focused on failure, because that is the part that gets skipped.
 *
 * Runs in node rather than jsdom: this code touches fetch and streams, not the
 * DOM, and jsdom startup dominates the runtime.
 *
 * The happy path is easy and gets exercised by hand. What matters is what the
 * user sees when the backend is down, dies mid-reply, or sends something
 * malformed. Each of those is asserted here against the real parsing code.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { streamChat, ChatTransportError, type ChatEvent } from './chatClient';

/** Build a Response whose body streams the given byte chunks. */
function streamingResponse(chunks: (string | Uint8Array)[], init: ResponseInit = {}) {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) {
        controller.enqueue(typeof c === 'string' ? encoder.encode(c) : c);
      }
      controller.close();
    },
  });
  return new Response(body, { status: 200, ...init });
}

/** A body that emits some chunks and then drops the connection.
 *
 *  The error must be raised from a later `pull`, not from `start`. Erroring the
 *  controller discards anything still queued, so doing it up front models a
 *  connection that failed before sending — not one that failed part-way. */
function droppingResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  let i = 0;
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i++]));
        return;
      }
      controller.error(new Error('socket hang up'));
    },
  });
  return new Response(body, { status: 200 });
}

const line = (o: unknown) => JSON.stringify(o) + '\n';
const token = (c: string) => line({ type: 'token', data: { content: c } });
const done = () => line({ type: 'done', data: {} });

async function collect(gen: AsyncGenerator<ChatEvent>): Promise<ChatEvent[]> {
  const out: ChatEvent[] = [];
  for await (const e of gen) out.push(e);
  return out;
}

// Widened to take the request. A zero-argument implementation is still
// assignable -- TypeScript accepts a function that ignores parameters -- so
// every existing caller is unchanged, and a test that needs to assert what was
// *sent* no longer has to stub `fetch` by hand.
const mockFetch = (
  impl: (url: string, init: RequestInit) => Promise<Response> | Response,
) => {
  vi.stubGlobal('fetch', vi.fn(impl));
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('parsing', () => {
  it('keeps model thinking off the answer channel', async () => {
    // Not a rendering preference. `token` events accumulate into
    // `streamingText`, which is what gets committed to the transcript and what
    // `pushSpeech` hands to Kokoro — so a reasoning event arriving as a token
    // would be the model's working read aloud in avatar mode. The two must stay
    // separate all the way down.
    mockFetch(() =>
      streamingResponse([
        line({ type: 'reasoning', data: { content: 'The rate is 400.' } }),
        token('Your day rate is 400.'),
        done(),
      ]),
    );

    const events = await collect(streamChat({ text: 'what is my rate' }));
    expect(events.map((e) => e.type)).toEqual(['reasoning', 'token', 'done']);
    expect(events[0]).toMatchObject({ content: 'The rate is 400.' });

    const spoken = events
      .filter((e): e is Extract<ChatEvent, { type: 'token' }> => e.type === 'token')
      .map((e) => e.content)
      .join('');
    expect(spoken).toBe('Your day rate is 400.');
    expect(spoken).not.toContain('The rate is 400.');
  });

  it('yields tokens and sources in arrival order', async () => {
    mockFetch(() =>
      streamingResponse([
        line({ type: 'source', data: { kind: 'memory', url: 'memory:1', title: 'a fact' } }),
        token('Hello '),
        token('world'),
        done(),
      ]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events.map((e) => e.type)).toEqual(['source', 'token', 'token', 'done']);
    expect(events[0]).toMatchObject({
      source: { kind: 'memory', url: 'memory:1', title: 'a fact' },
    });
  });

  it('carries the answering model, and its locality, ahead of the tokens', async () => {
    // The order is the assertion. It arrives before the first token so the
    // attribution is on screen while the reply is read.
    mockFetch(() =>
      streamingResponse([
        line({
          type: 'answering',
          data: {
            model: 'anthropic/claude-sonnet-4.5',
            locality: 'cloud',
            provider: 'openrouter',
            chosen_by: 'settings',
          },
        }),
        token('Hi'),
        done(),
      ]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events.map((e) => e.type)).toEqual(['answering', 'token', 'done']);
    expect(events[0]).toMatchObject({
      model: 'anthropic/claude-sonnet-4.5',
      locality: 'cloud',
      provider: 'openrouter',
      chosenBy: 'settings',
    });
  });

  it('reports an unresolved locality as null rather than as local', async () => {
    // The whole reason locality is three-valued. Coercing null to "local"
    // would tell the user their data stayed on the machine on the strength of
    // a lookup that failed — a confident false claim about the one field they
    // are most likely to check.
    mockFetch(() =>
      streamingResponse([
        line({ type: 'answering', data: { model: 'something-unrecognised', locality: null } }),
        done(),
      ]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events[0]).toMatchObject({ model: 'something-unrecognised', locality: null });
  });

  it('drops an attribution that names no model', async () => {
    // The backend sends the event whether or not it resolved a name, because
    // the absence is worth knowing there. Here there is nothing to draw.
    mockFetch(() =>
      streamingResponse([line({ type: 'answering', data: { model: '' } }), token('x'), done()]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events.map((e) => e.type)).toEqual(['token', 'done']);
  });

  it('reassembles a JSON object split across chunk boundaries', async () => {
    // The single most likely transport bug: chunks do not respect line breaks.
    const whole = token('reassembled');
    const cut = Math.floor(whole.length / 2);
    mockFetch(() => streamingResponse([whole.slice(0, cut), whole.slice(cut), done()]));

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events).toContainEqual({ type: 'token', content: 'reassembled' });
  });

  it('reassembles a multi-byte character split across chunk boundaries', async () => {
    // '£' is two bytes in UTF-8. Decoding each chunk independently corrupts it.
    const bytes = new TextEncoder().encode(token('£40,000'));
    const idx = bytes.indexOf(0xc2); // first byte of '£'
    mockFetch(() =>
      streamingResponse([bytes.slice(0, idx + 1), bytes.slice(idx + 1), done()]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events).toContainEqual({ type: 'token', content: '£40,000' });
  });

  it('skips a malformed line without losing the rest of the reply', async () => {
    mockFetch(() =>
      streamingResponse([token('before '), '{not json at all\n', token('after'), done()]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    const text = events
      .filter((e): e is Extract<ChatEvent, { type: 'token' }> => e.type === 'token')
      .map((e) => e.content)
      .join('');
    expect(text).toBe('before after');
  });

  it('ignores internal event types it does not model', async () => {
    mockFetch(() =>
      streamingResponse([
        line({ type: 'step_start', data: { capability_id: 'reasoning.generate' } }),
        line({ type: 'plan_complete', data: { state: 'completed' } }),
        token('answer'),
        done(),
      ]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events.map((e) => e.type)).toEqual(['token', 'done']);
  });

  it('handles a final line with no trailing newline', async () => {
    mockFetch(() =>
      streamingResponse([token('x'), JSON.stringify({ type: 'done', data: {} })]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events.map((e) => e.type)).toEqual(['token', 'done']);
  });
});

describe('failure', () => {
  it('reports an unreachable backend in plain language', async () => {
    mockFetch(() => Promise.reject(new TypeError('Failed to fetch')));

    await expect(collect(streamChat({ text: 'hi' }))).rejects.toThrow(
      /Could not reach the Zaram backend/,
    );
  });

  it('reports a dead upstream behind the dev proxy as unreachable', async () => {
    // Verified live: with the backend stopped, the Vite proxy answers 500 with
    // an empty body rather than refusing the connection, so fetch resolves and
    // the network-error branch never runs. Without this, the user is told
    // "Backend returned 500" instead of that the backend is not running.
    mockFetch(() => new Response('', { status: 500, statusText: 'Internal Server Error' }));

    await expect(collect(streamChat({ text: 'hi' }))).rejects.toThrow(
      /Could not reach the Zaram backend/,
    );
  });

  it('surfaces an HTTP error status with the backend detail', async () => {
    mockFetch(
      () =>
        new Response(JSON.stringify({ detail: 'Kernel not ready' }), {
          status: 503,
          statusText: 'Service Unavailable',
        }),
    );

    await expect(collect(streamChat({ text: 'hi' }))).rejects.toThrow(
      /503.*Kernel not ready/s,
    );
  });

  it('delivers a mid-stream backend error as an event, not an exception', async () => {
    // Tokens may already have arrived. Throwing would discard a partial answer
    // the backend genuinely produced.
    mockFetch(() =>
      streamingResponse([
        token('partial '),
        line({ type: 'error', data: { content: 'model timed out' } }),
        done(),
      ]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events).toContainEqual({ type: 'error', message: 'model timed out' });
    expect(events).toContainEqual({ type: 'token', content: 'partial ' });
  });

  it('flags a dropped connection as partial when text had already arrived', async () => {
    mockFetch(() => droppingResponse([token('half an ans')]));

    const gen = streamChat({ text: 'hi' });
    const seen: ChatEvent[] = [];
    let caught: unknown;
    try {
      for await (const e of gen) seen.push(e);
    } catch (err) {
      caught = err;
    }

    expect(caught).toBeInstanceOf(ChatTransportError);
    expect((caught as ChatTransportError).partial).toBe(true);
    // The tokens that did arrive are still delivered and must be kept.
    expect(seen).toContainEqual({ type: 'token', content: 'half an ans' });
  });

  it('rejects a stream that ends without done, rather than showing it as complete', async () => {
    // A truncated reply that looks finished is worse than a visible error.
    mockFetch(() => streamingResponse([token('cut off here')]));

    await expect(collect(streamChat({ text: 'hi' }))).rejects.toThrow(
      /ended unexpectedly/,
    );
  });

  it('ends quietly when aborted', async () => {
    // A deliberate cancellation is not a failure and must not raise.
    const controller = new AbortController();
    mockFetch(() => {
      controller.abort();
      return Promise.reject(
        new DOMException('The operation was aborted.', 'AbortError'),
      );
    });

    const events = await collect(streamChat({ text: 'hi' }, controller.signal));
    expect(events).toEqual([]);
  });
});

describe('the request body', () => {
  /**
   * Nothing here asserted what was *sent* — only what came back — and that is
   * how `model: 'gemma3:latest'` survived in this transport for months. It
   * overrode the provider layer's vetted selection on every message, with its
   * residency and data-policy gates already applied, and made choosing any
   * other model impossible from the interface however the backend was
   * configured. The tests were all green throughout.
   */
  const sent = (fetchMock: ReturnType<typeof vi.fn>) =>
    JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body)) as Record<string, unknown>;

  it('names no model when the caller expressed no preference', async () => {
    const fetchMock = vi.fn(() => streamingResponse([done()]));
    vi.stubGlobal('fetch', fetchMock);

    await collect(streamChat({ text: 'hi' }));

    // Empty, never a model name. Empty means "this request has no opinion", and
    // the backend then uses the chosen model or its own selection. A literal
    // here silently wins over both.
    expect(sent(fetchMock).model).toBe('');
  });

  it('passes the caller’s model through untouched', async () => {
    const fetchMock = vi.fn(() => streamingResponse([done()]));
    vi.stubGlobal('fetch', fetchMock);

    // Provider-prefixed, because that is the real shape of a discovered cloud
    // model id and the transport must not try to be clever about it.
    await collect(streamChat({ text: 'hi', model: 'openai:gpt-4o' }));

    expect(sent(fetchMock).model).toBe('openai:gpt-4o');
  });
});

describe('the model-load verdict is carried whole', () => {
  /**
   * `SwapPlan` has four kinds. `resident` is deliberately never sent, and this
   * parser listed two of the remaining three — so `oversized`, the verdict that
   * most needed saying, was discarded as unrecognised. What reached the user
   * for a model twice the size of their card was silence and then a read
   * timeout naming a URL.
   */
  it('passes an oversized verdict through rather than dropping it', async () => {
    mockFetch(() =>
      streamingResponse([
        line({
          type: 'model_load',
          data: { kind: 'oversized', model: 'gemma4:26b-a4b-it-q4_K_M', evicts: [] },
        }),
        token('ready'),
        done(),
      ]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events.map((e) => e.type)).toEqual(['model_load', 'token', 'done']);
    expect(events[0]).toMatchObject({
      kind: 'oversized',
      model: 'gemma4:26b-a4b-it-q4_K_M',
    });
  });

  it('carries `resident`, which is what cancels the warming guess', async () => {
    // **This test used to assert the opposite, and that is what kept the bug
    // alive.** It was written when `resident` was believed never to be sent.
    // The backend sends it on every reply whose model is already loaded, the
    // parser discarded it, and `chatStore`'s `resident` branch — whose only
    // job is to clear the timer that guesses silence means a cold model — was
    // unreachable. The orb read "Warming up" under a model that had not moved,
    // on every single message.
    //
    // Measured in the running app on 31 August 2026 with
    // `Qwen3.8-27B-exl3-2.20bpw` pinned and resident.
    mockFetch(() =>
      streamingResponse([
        line({ type: 'model_load', data: { kind: 'resident', model: 'gemma3', evicts: [] } }),
        token('hi'),
        done(),
      ]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events.map((e) => e.type)).toEqual(['model_load', 'token', 'done']);
    expect(events[0]).toMatchObject({ kind: 'resident', model: 'gemma3' });
  });

  it('still drops a kind it has no meaning for', async () => {
    // The list tracks `SwapPlan`'s four kinds. Anything else is dropped rather
    // than coerced, because a kind this client does not understand cannot be
    // rendered into a sentence about what the machine is doing.
    mockFetch(() =>
      streamingResponse([
        line({ type: 'model_load', data: { kind: 'defragmenting', model: 'gemma3', evicts: [] } }),
        token('hi'),
        done(),
      ]),
    );

    const events = await collect(streamChat({ text: 'hi' }));
    expect(events.map((e) => e.type)).toEqual(['token', 'done']);
  });
});

describe('the conversation this reply is written into', () => {
  /**
   * Without this the client never learns the id the backend opened, so every
   * message starts its own one-line thread — a transcript store with a caller
   * that cannot use it, which looks exactly like a working feature.
   */
  it('carries the id the backend opened', async () => {
    mockFetch(() =>
      streamingResponse([
        line({
          type: 'conversation',
          data: { conversation_id: 'conv_abc123', title: 'what is my day rate' },
        }),
        token('400 a day.'),
        done(),
      ]),
    );

    const events = await collect(streamChat({ text: 'what is my day rate' }));

    expect(events.map((e) => e.type)).toEqual(['conversation', 'token', 'done']);
    expect(events[0]).toMatchObject({
      conversationId: 'conv_abc123',
      title: 'what is my day rate',
    });
  });

  it('sends the conversation it is continuing', async () => {
    const seen: RequestInit[] = [];
    mockFetch((_url: string, init: RequestInit) => {
      seen.push(init);
      return streamingResponse([token('hi'), done()]);
    });

    await collect(streamChat({ text: 'and the terms?', conversationId: 'conv_abc123' }));

    expect(JSON.parse(String(seen[0].body)).conversation_id).toBe('conv_abc123');
  });

  it('sends an empty string when starting a new one', async () => {
    // Empty means "open one for me". Omitting the field entirely would leave
    // the backend defaulting, which is the same thing but says less.
    const seen: RequestInit[] = [];
    mockFetch((_url: string, init: RequestInit) => {
      seen.push(init);
      return streamingResponse([token('hi'), done()]);
    });

    await collect(streamChat({ text: 'hello' }));

    expect(JSON.parse(String(seen[0].body)).conversation_id).toBe('');
  });

  it('drops an event with no id rather than holding an empty one', async () => {
    mockFetch(() =>
      streamingResponse([
        line({ type: 'conversation', data: { conversation_id: '  ', title: 'x' } }),
        token('hi'),
        done(),
      ]),
    );

    const events = await collect(streamChat({ text: 'hello' }));

    expect(events.map((e) => e.type)).toEqual(['token', 'done']);
  });
});
