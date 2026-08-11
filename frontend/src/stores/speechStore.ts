import { create } from 'zustand';
import { useOrbStore } from './orbStore';
import { toVisemeTrack, type VisemeCue, type WordTiming } from '@/lib/visemes';
import { splitIntoUtterances } from '@/lib/utterances';

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

  speak: (text: string, voice?: string) => Promise<void>;
  stop: () => void;
}

/** Bumped by `stop()` and by each new `speak()`. Every async step checks it
 *  before touching state, so a reply that begins while another is still
 *  speaking cannot have its audio interleaved by the older one's callbacks. */
let generation = 0;

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
      // Reported rather than swallowed, so the UI can name the fix and its
      // size the way the OCR extra does.
      return {
        error:
          res.status === 503
            ? 'Speech is not installed.'
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
    get().stop();
    const mine = ++generation;
    const setOrbState = useOrbStore.getState().setOrbState;

    const pieces = splitIntoUtterances(text);
    if (pieces.length === 0) return;

    set({ error: null });
    setOrbState('speaking');

    // One piece ahead, no more. Two would synthesise work that a `stop()` is
    // about to discard, and Kokoro is the scarce resource here.
    let pending = synthesise(pieces[0], voice, mine);

    for (let i = 0; i < pieces.length; i++) {
      const current = await pending;
      if (generation !== mine) return;

      pending =
        i + 1 < pieces.length
          ? synthesise(pieces[i + 1], voice, mine)
          : Promise.resolve(null);

      if (current === null) return;
      if ('error' in current) {
        set({ error: current.error });
        // The first piece failing is the whole utterance failing; a later one
        // failing has already said something, and stopping there is better
        // than pressing on through a gap the listener will hear as a fault.
        break;
      }

      set({ audio: current.audio, track: current.track });
      await playToEnd(current.audio);
      URL.revokeObjectURL(current.objectUrl);

      if (generation !== mine) return;
    }

    if (generation !== mine) return;
    // Only stand down if nothing else has taken the state in the meantime.
    if (useOrbStore.getState().orbState === 'speaking') setOrbState('idle');
    set({ audio: null, track: [] });
  },

  stop: () => {
    generation++;
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
