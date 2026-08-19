import { create } from 'zustand';
import { useOrbStore } from './orbStore';
import { toVisemeTrack, type VisemeCue, type WordTiming } from '@/lib/visemes';
import { takeCompleteUtterances } from '@/lib/utterances';
import { stripCitationMarkers } from '@/lib/markers';

/**
 * Zaram speaking, and the mouth shapes that go with it.
 *
 * One store, because speech is a property of the system rather than of a
 * renderer. It sets `orbStore` to `speaking`, so the orb and the avatar both
 * react to the same fact — the orb pulses, the avatar's mouth moves — and a
 * third renderer would need no changes here. That is the same seam
 * `useEmbodimentState()` establishes, applied to audio.
 *
 * **Timings arrive with the audio, never before it.** `docs/EMBODIMENT-SPIKE.md`
 * records this as a correction to an earlier assumption: misaki's G2P knows
 * *what* sounds, not *when*, and the durations are a model output filled in
 * from `pred_dur` on the same forward pass that produces the waveform. So there
 * is no "timings first, audio second" sequence to build against. One request,
 * one payload. The renderer's problem is playback alignment, not prediction.
 *
 * Speaking in pieces, and why
 * ---------------------------
 * This used to make **one blocking request for the whole reply**, so nothing
 * was heard until every word of it had been synthesised. Kokoro on CPU runs at
 * roughly real time — measured 10 August 2026: 1.25s of audio took 3.4s, a
 * 30-word passage took 8.2s — so the wait scaled with the length of the answer.
 * A twenty-second reply meant twenty-odd seconds of silence first. That is the
 * delay, and it was architectural rather than a slow model: local inference's
 * advantage was being spent waiting for audio nobody needed yet.
 *
 * Now the reply is split into sentences and **the next piece is synthesised and
 * downloaded while the current one plays**. Time-to-first-sound stops scaling
 * with reply length and becomes the cost of one sentence.
 *
 * The prefetch downloads the bytes, not just the URL. Handing `new Audio(url)`
 * a fresh URL at the moment the previous clip ends puts an HTTP round trip
 * inside the gap between sentences, which is audible; fetching to a blob during
 * the previous sentence puts it where there is time to spare.
 *
 * What this does not fix: synthesis is still real-time-ish on CPU, so a reply
 * of many short sentences can still out-run it and pause mid-way. That is a
 * throughput problem and needs the model somewhere faster, which is a VRAM
 * decision (`CLAUDE.md`) rather than a change here.
 */

const API = import.meta.env.VITE_ZARAM_API ?? '';

/** One synthesised piece, ready to play with nothing left to download. */
interface Utterance {
  audio: HTMLAudioElement;
  track: VisemeCue[];
  /** Revoked after playback; a blob URL held forever is a leak of the whole clip. */
  objectUrl: string;
}

interface SpeechStore {
  /** The element currently playing. The renderer reads `currentTime` off this
   *  every frame rather than storing a time in React — a 60 Hz state update
   *  would re-render the whole tree to move a jaw. */
  audio: HTMLAudioElement | null;
  /** Mouth shapes for the piece in flight. Empty when the engine could not
   *  produce timings, which is a supported answer and not an error: a renderer
   *  checks and falls back rather than branching on absence. */
  track: VisemeCue[];
  /** Why speech is unavailable, when it is. Named, never silent. */
  error: string | null;

  /** Speak a complete piece of text. Used by the speak-aloud button, where the
   *  whole reply already exists. */
  speak: (text: string, voice?: string) => Promise<void>;

  /** Start speaking a reply that is still being generated.
   *
   *  Call `pushSpeech` as tokens arrive and `endSpeech` when the stream ends.
   *  Returns immediately; playback runs on its own. */
  beginSpeech: (voice?: string) => void;
  /** Hand over the reply so far. Safe to call on every token: only sentences
   *  that will not change again are queued, the rest is held. */
  pushSpeech: (replySoFar: string) => void;
  /** No more text is coming. Flushes whatever is held. */
  endSpeech: () => void;

  stop: () => void;

  /**
   * Stop speaking because the user did something, rather than because the
   * reply ended.
   *
   * A separate name from `stop()` on purpose. `stop()` is the mechanism and is
   * called on every `beginSpeech`, on cancel, on teardown; this is the
   * *intent*, and separating them means a call site reads as "the user
   * interrupted" rather than "something reset the audio". They do the same
   * thing today. When they stop doing the same thing — a resume, a fade rather
   * than a cut, a record that the user interrupts often — this is the one that
   * changes, and every barge-in site changes with it for free.
   *
   * Cheap when nothing is speaking, so callers may fire it on every keystroke
   * without checking first. A caller that has to ask "is it speaking?" before
   * interrupting is a caller that will eventually get the check wrong.
   */
  bargeIn: () => void;
}

/**
 * The pieces waiting to be synthesised, which may not all exist yet.
 *
 * The play loop used to walk a fixed array, which is correct when the whole
 * reply is known and useless while it is still arriving. This is the same loop
 * over a queue that can grow underneath it: `next()` waits when the queue is
 * empty rather than ending, and only ends once the producer has said there is
 * no more coming.
 */
class UtteranceQueue {
  private items: string[] = [];
  private closed = false;
  private waiting: (() => void) | null = null;

  push(text: string): void {
    this.items.push(text);
    this.wake();
  }

  close(): void {
    this.closed = true;
    this.wake();
  }

  private wake(): void {
    const w = this.waiting;
    this.waiting = null;
    w?.();
  }

  /** The next piece, or null once the queue is closed and drained. */
  async next(): Promise<string | null> {
    while (this.items.length === 0) {
      if (this.closed) return null;
      await new Promise<void>((resolve) => {
        this.waiting = resolve;
      });
    }
    return this.items.shift() ?? null;
  }
}

/** The queue the current generation is reading from. */
let queue: UtteranceQueue | null = null;
/** The reply so far, markers stripped, as last handed over. */
let spokenSoFar = '';
/** How many characters of it have already been queued as utterances. */
let consumed = 0;

/** Bumped by `stop()` and by each new `speak()`. Every async step checks it
 *  before touching state, so a reply that begins while another is still
 *  speaking cannot have its audio interleaved by the older one's callbacks. */
let generation = 0;

/**
 * What the user is told when speech is not installed.
 *
 * The command and the size, in that order, because "install the extra" is not
 * a decision somebody on metered data can make without the megabytes. Exported
 * so the assertion in the test names the same string the user sees rather than
 * a copy of it — a test that hardcodes the wording passes after the wording
 * stops saying anything.
 */
export const SPEECH_NOT_INSTALLED =
  'Speech is not installed: pip install -r backend/requirements-voice.txt (905 MB, one time).';

async function synthesise(
  text: string,
  voice: string | undefined,
  mine: number,
): Promise<Utterance | { error: string } | null> {
  let payload: { audio_url?: string; timings?: WordTiming[] };
  try {
    const res = await fetch(`${API}/voice/synthesize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice }),
    });
    if (!res.ok) {
      // 503 is the honest and common case: the voice extra is not installed.
      //
      // The comment here used to say this was reported "so the UI can name the
      // fix and its size the way the OCR extra does", above a string that did
      // neither — it said only "Speech is not installed." A reader learns from
      // that that speech is broken, not that it is one command away, and on a
      // metered connection the size is the half that decides. Now it reads
      // like `ingest/quality.py`'s OCR line, which is the shape this was
      // always describing.
      return {
        error:
          res.status === 503
            ? SPEECH_NOT_INSTALLED
            : `Speech failed (${res.status}).`,
      };
    }
    payload = await res.json();
  } catch (e) {
    return { error: e instanceof Error ? e.message : 'Speech request failed.' };
  }

  if (generation !== mine) return null;
  if (!payload.audio_url) return { error: 'Speech returned no audio.' };

  // Download here rather than letting the element fetch on play: this runs
  // while the previous sentence is still speaking, which is exactly the time
  // there is to spend.
  let objectUrl: string;
  try {
    const clip = await fetch(`${API}${payload.audio_url}`);
    if (!clip.ok) return { error: `The audio could not be fetched (${clip.status}).` };
    objectUrl = URL.createObjectURL(await clip.blob());
  } catch (e) {
    return { error: e instanceof Error ? e.message : 'The audio could not be fetched.' };
  }

  if (generation !== mine) {
    URL.revokeObjectURL(objectUrl);
    return null;
  }

  const audio = new Audio(objectUrl);
  audio.preload = 'auto';
  return { audio, track: toVisemeTrack(payload.timings ?? []), objectUrl };
}

/** Resolves when the clip finishes, or fails. Never rejects: a clip that will
 *  not play must not strand the pieces queued behind it. */
function playToEnd(audio: HTMLAudioElement): Promise<void> {
  return new Promise((resolve) => {
    const done = () => {
      audio.removeEventListener('ended', done);
      audio.removeEventListener('error', done);
      resolve();
    };
    audio.addEventListener('ended', done);
    audio.addEventListener('error', done);
    void audio.play().catch(() => done());
  });
}

export const useSpeechStore = create<SpeechStore>((set, get) => ({
  audio: null,
  track: [],
  error: null,

  speak: async (text, voice) => {
    // The whole reply is already known, so this is the streaming path with
    // everything pushed at once. One loop, not two — a second copy of the
    // play-and-prefetch sequence is where the two would drift.
    get().beginSpeech(voice);
    get().pushSpeech(text);
    get().endSpeech();
  },

  beginSpeech: (voice) => {
    get().stop();
    const mine = ++generation;
    const mineQueue = new UtteranceQueue();
    queue = mineQueue;
    spokenSoFar = '';
    consumed = 0;

    set({ error: null });
    // Deliberately *not* `setOrbState('speaking')` here — corrected 19 August
    // 2026. This runs before the first token exists, and synthesis takes
    // seconds, so it claimed sound that had not started. It also fought the
    // stream: `ChatSurface` writes `thinking` as soon as the request is in
    // flight, so the eager claim was overwritten anyway and the state was a
    // lie in both directions. The state is now set where it is true — at the
    // moment a clip begins to play, below.

    // Drives itself. The caller pushes text and walks away, because speech is
    // an accompaniment to the reply and must never be something the reply has
    // to wait for.
    void (async () => {
      const setOrbState = useOrbStore.getState().setOrbState;

      // One piece ahead, no more. Two would synthesise work that a `stop()` is
      // about to discard, and Kokoro is the scarce resource here.
      const first = await mineQueue.next();
      if (first === null || generation !== mine) {
        if (generation === mine && useOrbStore.getState().orbState === 'speaking') {
          setOrbState('idle');
        }
        return;
      }

      let pending: Promise<Utterance | { error: string } | null> = synthesise(
        first,
        voice,
        mine,
      );

      for (;;) {
        const current = await pending;
        if (generation !== mine) return;

        // Ask for the next piece *before* playing this one. On a live stream it
        // may not exist yet, and waiting for it here — rather than after
        // playback — is what lets synthesis overlap the model still generating.
        const upcoming = await mineQueue.next();
        if (generation !== mine) return;
        pending =
          upcoming === null
            ? Promise.resolve(null)
            : synthesise(upcoming, voice, mine);

        if (current === null) break;
        if ('error' in current) {
          set({ error: current.error });
          // The first piece failing is the whole utterance failing; a later one
          // failing has already said something, and stopping there is better
          // than pressing on through a gap the listener will hear as a fault.
          break;
        }

        set({ audio: current.audio, track: current.track });
        // Sound is about to come out, so now it is true. The avatar reads this
        // to open its mouth and reads `audio.currentTime` to decide the shape;
        // both need the clip in the store *before* the state says speaking, or
        // the first frames scrub against the previous utterance.
        setOrbState('speaking');
        await playToEnd(current.audio);
        URL.revokeObjectURL(current.objectUrl);

        if (generation !== mine) return;
        if (upcoming === null) break;
      }

      if (generation !== mine) return;
      // Only stand down if nothing else has taken the state in the meantime.
      if (useOrbStore.getState().orbState === 'speaking') setOrbState('idle');
      set({ audio: null, track: [] });
    })();
  },

  pushSpeech: (replySoFar) => {
    if (!queue) return;
    // Citation markers are display chrome and were being read aloud: nothing
    // stripped them on this path, so Kokoro pronounced "[M1]" mid-sentence.
    // `ChatSurface` and `SpeakButton` both strip for their own reasons; this is
    // the third caller and the only one that had been missed.
    const spoken = stripCitationMarkers(replySoFar);
    if (spoken.length <= consumed) return;

    spokenSoFar = spoken;
    // A character cursor rather than a held string. The caller hands over the
    // whole reply every time, so the only safe record of what has been said is
    // how far into that text we have got — and `rest` is a suffix of what was
    // passed in, which is what makes the arithmetic below exact.
    const { ready, rest } = takeCompleteUtterances(spoken.slice(consumed));
    consumed = spoken.length - rest.length;
    for (const piece of ready) queue.push(piece);
  },

  endSpeech: () => {
    if (!queue) return;
    const { ready } = takeCompleteUtterances(spokenSoFar.slice(consumed), true);
    for (const piece of ready) queue.push(piece);
    consumed = spokenSoFar.length;
    queue.close();
    queue = null;
  },

  bargeIn: () => {
    // No-op unless something is actually playing or queued, so the composer can
    // call this on every keystroke without churning state or clearing an error
    // the user has not read yet.
    if (get().audio === null && queue === null) return;
    get().stop();
  },

  stop: () => {
    generation++;
    // Release anything the loop is blocked on, or it waits for a queue nobody
    // will ever push to again — a leaked promise per interrupted reply.
    queue?.close();
    queue = null;
    spokenSoFar = '';
    consumed = 0;
    const { audio } = get();
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    if (useOrbStore.getState().orbState === 'speaking') {
      useOrbStore.getState().setOrbState('idle');
    }
    set({ audio: null, track: [] });
  },
}));
