/**
 * @vitest-environment jsdom
 *
 * `speaking` is true while sound comes out, and only then.
 *
 * Reported 5 October 2026, after several attempts: *"the avatar doesn't type
 * on the coding state."* The loop waited for the next sentence to exist before
 * playing the current one, and kept `speaking` raised while it waited. Code is
 * never spoken, so a reply with two sentences before its code block left the
 * avatar in its talking pose, silent, for as long as the block took to write —
 * and `speaking` is drawn over `coding`, so it never typed.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useOrbStore } from './orbStore';
import { SPEECH_GAP_MS, useSpeechStore } from './speechStore';

/** Audio that plays until the test says it has ended: `play`, `pause`, and
 *  the `ended` and `error` events, which is all `playToEnd` uses. */
class FakeAudio {
  static all: FakeAudio[] = [];
  preload = '';
  currentTime = 0;
  playing = false;
  private listeners = new Map<string, Set<() => void>>();
  constructor(public src: string) {
    FakeAudio.all.push(this);
  }
  addEventListener(type: string, fn: () => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(fn);
  }
  removeEventListener(type: string, fn: () => void) {
    this.listeners.get(type)?.delete(fn);
  }
  play() {
    this.playing = true;
    return Promise.resolve();
  }
  pause() {
    this.playing = false;
  }
  end() {
    this.playing = false;
    for (const fn of [...(this.listeners.get('ended') ?? [])]) fn();
  }
}

const speaking = () => useOrbStore.getState().speaking;
const playing = () => FakeAudio.all.filter((a) => a.playing);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Sentences of at least 24 characters, so the utterance splitter keeps them
 *  apart (`lib/utterances.ts` merges shorter ones into their neighbour). */

/** Poll on real timers until `ready()` holds. */
async function until(ready: () => boolean, what: string, ms = 3000): Promise<void> {
  const deadline = Date.now() + ms;
  while (!ready()) {
    if (Date.now() > deadline) throw new Error(`timed out waiting for ${what}`);
    await sleep(20);
  }
}

beforeEach(() => {
  FakeAudio.all = [];
  vi.stubGlobal('Audio', FakeAudio);
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      String(url).endsWith('/voice/synthesize')
        ? new Response(JSON.stringify({ audio_url: '/audio/clip.wav', timings: [] }), { status: 200 })
        : new Response(new Blob(['x']), { status: 200 }),
    ),
  );
  URL.createObjectURL = vi.fn(() => 'blob:clip');
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
  useSpeechStore.getState().stop();
  vi.unstubAllGlobals();
});

describe('speech and the state under it', () => {
  it('stands down while the model writes code, so the state under it shows', async () => {
    const s = useSpeechStore.getState();
    s.beginSpeech();
    s.pushSpeech('Here is the plan for the whole game. I will write the full page for you now. ```html\n<div>');

    await until(() => playing().length === 1, 'the first sentence');
    expect(speaking()).toBe(true);
    playing()[0].end();
    await until(() => playing().length === 1, 'the second sentence');
    expect(speaking()).toBe(true);

    // The second sentence ends; the rest of the reply is still code.
    playing()[0].end();
    await sleep(SPEECH_GAP_MS + 100);
    expect(speaking()).toBe(false);

    // More code arrives: still nothing to say.
    s.pushSpeech('Here is the plan for the whole game. I will write the full page for you now. ```html\n<div>\n<canvas></canvas>');
    await sleep(50);
    expect(speaking()).toBe(false);

    // Prose after the block is spoken, and speaking returns with the sound.
    s.pushSpeech('Here is the plan for the whole game. I will write the full page for you now. ```html\n<div>\n<canvas></canvas>\n</div>\n```\n\nThe page is ready for you to play now.');
    s.endSpeech();
    await until(() => playing().length === 1, 'the closing sentence');
    expect(speaking()).toBe(true);
    playing()[0].end();
    await until(() => !speaking(), 'speaking to stand down');
  });

  it('does not flicker between two sentences that follow each other', async () => {
    const s = useSpeechStore.getState();
    s.beginSpeech();
    s.pushSpeech('This first sentence is long enough to stand alone. The second one follows it straight away. ');
    s.endSpeech();

    await until(() => playing().length === 1, 'the first sentence');
    const seen: boolean[] = [];
    const off = useOrbStore.subscribe((st) => seen.push(st.speaking));
    playing()[0].end();
    await until(() => playing().length === 1, 'the second sentence');
    off();
    // The next clip was ready inside the grace, so speaking never dropped.
    expect(seen).not.toContain(false);
  });
});
