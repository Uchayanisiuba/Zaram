import { create } from 'zustand';
import { useOrbStore } from './orbStore';
import { toVisemeTrack, type VisemeCue, type WordTiming } from '@/lib/visemes';

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
 * is no "timings first, audio second" sequence to build against, no lead-in
 * during which the mouth could start shaping a word before the sound exists,
 * and no state where a caller holds timings without their audio. One request,
 * one payload. The renderer's problem is playback alignment, not prediction.
 */

const API = import.meta.env.VITE_ZARAM_API ?? '';

interface SpeechStore {
  /** The element currently playing. The renderer reads `currentTime` off this
   *  every frame rather than storing a time in React — a 60 Hz state update
   *  would re-render the whole tree to move a jaw. */
  audio: HTMLAudioElement | null;
  /** Mouth shapes for the utterance in flight. Empty when the engine could not
   *  produce timings, which is a supported answer and not an error: a renderer
   *  checks and falls back rather than branching on absence. */
  track: VisemeCue[];
  /** Why speech is unavailable, when it is. Named, never silent. */
  error: string | null;

  speak: (text: string, voice?: string) => Promise<void>;
  stop: () => void;
}

export const useSpeechStore = create<SpeechStore>((set, get) => ({
  audio: null,
  track: [],
  error: null,

  speak: async (text, voice) => {
    get().stop();
    const setOrbState = useOrbStore.getState().setOrbState;

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
        set({ error: res.status === 503 ? 'Speech is not installed.' : `Speech failed (${res.status}).` });
        return;
      }
      payload = await res.json();
    } catch (e) {
      set({ error: e instanceof Error ? e.message : 'Speech request failed.' });
      return;
    }

    if (!payload.audio_url) {
      set({ error: 'Speech returned no audio.' });
      return;
    }

    const audio = new Audio(`${API}${payload.audio_url}`);
    const track = toVisemeTrack(payload.timings ?? []);

    const finish = () => {
      // Only stand down if nothing else has taken the state in the meantime.
      // A reply that begins while the previous one is still speaking would
      // otherwise be reset to idle by the older utterance ending.
      if (useOrbStore.getState().orbState === 'speaking') setOrbState('idle');
      set({ audio: null, track: [] });
    };
    audio.addEventListener('ended', finish);
    audio.addEventListener('error', () => {
      set({ error: 'The audio could not be played.' });
      finish();
    });

    set({ audio, track, error: null });
    setOrbState('speaking');
    try {
      await audio.play();
    } catch (e) {
      // Autoplay policy, most likely. Real, and the user has to be told rather
      // than left watching a silent mouth.
      set({ error: e instanceof Error ? e.message : 'Playback was blocked.' });
      finish();
    }
  },

  stop: () => {
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
