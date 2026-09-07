import { create } from 'zustand';

import {
  VoiceActivityDetector,
  rmsOf,
} from '@/lib/voiceActivity';
import { useSpeechStore } from '@/stores/speechStore';

/**
 * Zaram listening — the mirror of `speechStore`.
 *
 * The recording is made by the browser, sent to Zaram's own backend, and
 * transcribed there by faster-whisper on this machine. Nothing reaches a third
 * party, which is the entire reason this is thirty lines of MediaRecorder
 * plumbing rather than the three lines of `webkitSpeechRecognition` that
 * `scripts/check-no-cloud-speech.mjs` bans: that API streams the user's *audio*
 * — not a transcript — to Google, where no gate can see or log it.
 *
 * **The microphone is released on every exit path.** Not tidiness: the browser's
 * recording indicator is the only signal the user has that Zaram is listening,
 * and a product whose claim is that you can see what it does must not leave that
 * light on after it has stopped caring. Every route out of `_teardown` goes
 * through it, including the failures.
 *
 * Local recording state — the recorder, the stream, the chunks — is module
 * scope rather than store state. No renderer reads it, and putting a
 * MediaRecorder in a zustand store would publish an object whose identity
 * changes on every frame of a recording to everything subscribed.
 */

const API = import.meta.env.VITE_ZARAM_API ?? '';

/** What the button is doing, in the order it happens. */
export type MicStatus = 'idle' | 'requesting' | 'recording' | 'transcribing';

/**
 * How the microphone was asked for, which decides when it closes.
 *
 * * **`push`** — one utterance. Pressed to start, pressed to stop, and the
 *   microphone is released the moment the recording ends. This is what the
 *   control has always done and it stays the default and the click gesture.
 * * **`latched`** — a conversation. The microphone stays open across turns,
 *   each utterance is cut on silence and transcribed on its own, and Zaram's
 *   voice yields the moment the user starts talking.
 *
 * **Two modes and not a setting**, because the difference is *this exchange*
 * rather than a standing preference: rule 7h, offer at the moment of doubt and
 * never make the user choose in advance. Latched is entered by a gesture and
 * leaves by one.
 */
export type MicMode = 'push' | 'latched';

/** How often the loudness of the room is read while latched, in ms.
 *
 *  An interval rather than `requestAnimationFrame`, deliberately.
 *  `requestAnimationFrame` stops in a background tab, so a latched microphone
 *  behind another window would keep the browser's recording light on and quietly
 *  stop hearing anything — a failure with no symptom, which is the kind this
 *  repository keeps paying for. 50 ms is four readings inside `ONSET_MS`, which
 *  is enough for the detector's duration rules to mean what they say. */
const LEVEL_INTERVAL_MS = 50;

/**
 * What the microphone is asked for.
 *
 * `echoCancellation` is the one that matters and it is why this is spelled out
 * rather than left as `{ audio: true }`. In a latched conversation the
 * microphone is open while Zaram is talking, so without it the recording
 * contains Zaram's own voice — which is transcribed and read back as something
 * the user said. The detector raises its bar while Zaram speaks as a second
 * line, but the browser's canceller is the first and it is free.
 *
 * All three are requests, not guarantees: a browser that ignores them still
 * gets a stream, which is right — refusing to listen because a hint was not
 * honoured would be worse than listening imperfectly.
 */
const AUDIO_CONSTRAINTS: MediaStreamConstraints = {
  audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
};

/** Preference order. The first supported one wins.
 *
 *  Opus in WebM is what Chromium produces and what PyAV decodes without any
 *  extra codec; `audio/mp4` is Safari's answer to the same question. The empty
 *  string is the honest last resort: MediaRecorder's own default, whatever that
 *  turns out to be, rather than refusing to record on a browser we did not
 *  anticipate. */
const PREFERRED_TYPES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', ''];

function pickMimeType(): string {
  if (typeof MediaRecorder === 'undefined') return '';
  for (const type of PREFERRED_TYPES) {
    if (type === '' || MediaRecorder.isTypeSupported(type)) return type;
  }
  return '';
}

/** Whether this browser can record at all. Checked rather than assumed: a
 *  missing capability must disable the control visibly, not fail on press. */
export function micSupported(): boolean {
  return (
    typeof MediaRecorder !== 'undefined' &&
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia
  );
}

let recorder: MediaRecorder | null = null;
let stream: MediaStream | null = null;
let chunks: Blob[] = [];

/** The listening half of latched mode: the analyser reading the room, the timer
 *  driving it, the detector deciding what it heard, and where a finished
 *  utterance is delivered.
 *
 *  Module scope for the same reason the recorder is: nothing renders these, and
 *  an `AudioContext` in a zustand store publishes an object to every subscriber
 *  whose contents change fifty times a second. */
let audioContext: AudioContext | null = null;
let analyser: AnalyserNode | null = null;
let levelTimer: ReturnType<typeof setInterval> | null = null;
let detector: VoiceActivityDetector | null = null;
let deliver: ((text: string) => void) | null = null;
/** Bumped on every exit from latched mode, so a transcription that was already
 *  in flight cannot deliver its text into a conversation the user has left —
 *  the same generation-counter discipline `speechStore` keeps for audio. */
let latchGeneration = 0;

/** Stop listening to the room. Leaves the microphone itself alone: the level
 *  meter and the recording are separate lifetimes, and a latched utterance
 *  being transcribed must not silence the meter for the next one. */
function stopListening(): void {
  if (levelTimer !== null) {
    clearInterval(levelTimer);
    levelTimer = null;
  }
  analyser = null;
  // `close()` returns a promise nobody waits on: there is nothing useful to do
  // with the result, and a failure here must not stop the microphone being
  // released below.
  void audioContext?.close().catch(() => undefined);
  audioContext = null;
  detector?.reset();
  detector = null;
}

/** Release the microphone and forget the recording. Always safe to call. */
function teardown(): void {
  if (recorder && recorder.state !== 'inactive') {
    try {
      recorder.stop();
    } catch {
      // Already stopping. Nothing to do; the tracks below are what matter.
    }
  }
  stopListening();
  deliver = null;
  stream?.getTracks().forEach((track) => track.stop());
  recorder = null;
  stream = null;
  chunks = [];
}

/** A recorder on the open stream, with its chunk sink wired. */
function armRecorder(): MediaRecorder | null {
  if (!stream) return null;
  const mimeType = pickMimeType();
  chunks = [];
  const next = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
  next.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };
  return next;
}

/** Stop `active` and hand back everything it captured.
 *
 *  `stop()` flushes a final `dataavailable` *before* `stop` fires, so the blob
 *  has to be assembled in the stop handler. Assembling it beside the call drops
 *  the last chunk — the end of the sentence. */
function finishRecording(active: MediaRecorder): Promise<Blob> {
  const type = active.mimeType || 'audio/webm';
  return new Promise<Blob>((resolve) => {
    active.onstop = () => resolve(new Blob(chunks, { type }));
    try {
      active.stop();
    } catch {
      resolve(new Blob(chunks, { type }));
    }
  });
}

interface MicStore {
  status: MicStatus;
  /** Whether this is one utterance or a conversation. See `MicMode`. */
  mode: MicMode;
  /** How loud the room is right now, 0..1, while latched. Zero otherwise.
   *
   *  Published so the control can show that Zaram is *hearing* something, which
   *  is the difference between a microphone that is on and one that is working.
   *  A latched microphone that had gone deaf would otherwise look identical to
   *  one waiting politely for you to speak. */
  level: number;
  /** Whether the detector believes the user is talking at this instant. */
  hearingVoice: boolean;
  /** Why Zaram cannot listen, as the backend phrased it. Written for the user —
   *  it names the install and its size, or the blocked download and its size —
   *  so it is rendered as-is rather than replaced with "unavailable". */
  unavailableReason: string | null;
  /** A failure of this attempt, as distinct from the capability being absent.
   *  A denied microphone permission is not a missing extra, and telling someone
   *  to install 81 MB when they clicked Block would be a wrong diagnosis. */
  error: string | null;
  /** Set when the last transcript contained an amount, a currency or a number.
   *
   *  Not a failure and not styled as one. Measured: the same sentence came back
   *  three different ways and one of them turned *naira* into **$**, wrong by
   *  about fifteen hundred times in the direction that looks reasonable on an
   *  invoice. Nothing downstream can catch that, because `$400,000` is a
   *  well-formed amount — so the only place it can be caught is here, by the
   *  person who said it, before they press send.
   *
   *  Cleared on the next recording, because it describes one transcript. */
  figureNotice: string | null;

  /** Ask the backend whether it can listen. Local call; no egress. */
  checkAvailability: () => Promise<void>;
  start: () => Promise<void>;
  /**
   * Open the microphone and keep it open, cutting an utterance on every pause.
   *
   * `onUtterance` is called with each transcript as it lands, which is how the
   * text reaches the composer without this store knowing one exists. It is
   * **not** a send: transcribed speech stays editable text, in latched mode as
   * in push mode, because a recogniser that mishears and then submits has
   * spoken for the user — and it does that far more often in a mode designed to
   * be left running.
   */
  startLatched: (onUtterance: (text: string) => void) => Promise<void>;
  /** Leave latched mode and release the microphone.
   *
   *  An utterance already being transcribed is allowed to finish and is then
   *  discarded, rather than cancelled: the request is in flight either way, and
   *  delivering text into a conversation the user has just left is the failure
   *  worth preventing. */
  stopLatched: () => void;
  /** Stop, transcribe, and return what was heard. Empty string when nothing
   *  was. The caller decides where the text goes — this store does not know
   *  about the composer. */
  stop: () => Promise<string>;
  /** Throw the recording away and release the microphone. */
  cancel: () => void;
}

/**
 * Post one recording to Zaram and return what it heard.
 *
 * **One transcription path for both modes**, extracted rather than copied. The
 * push path already carried three things a second implementation would get
 * wrong on its own: a 503 meaning the *capability* is missing rather than this
 * attempt, so the control disables itself with the reason instead of failing
 * again on the next press; the backend's own wording for a refusal, which
 * tracks the measurement that justifies it; and the figure notice, which is the
 * only place a dictated *naira* turning into a **$** can be caught. Latched mode
 * makes far more of these calls, so it is the last place that should have its
 * own copy of them.
 *
 * Writes the outcome into the store and returns the text, or `''`.
 */
async function transcribe(
  blob: Blob,
  type: string,
  set: (partial: Partial<MicStore>) => void,
): Promise<string> {
  if (blob.size === 0) return '';
  try {
    const res = await fetch(`${API}/voice/transcribe`, {
      method: 'POST',
      headers: { 'Content-Type': type },
      body: blob,
    });

    if (!res.ok) {
      const detail = await res
        .json()
        .then((b: { detail?: string }) => b.detail)
        .catch(() => undefined);
      if (res.status === 503) {
        set({ unavailableReason: detail ?? 'Zaram cannot listen yet.' });
      } else {
        set({ error: detail ?? `Transcription failed (${res.status}).` });
      }
      return '';
    }

    const body: {
      text?: string;
      needs_confirmation?: boolean;
      confirmation_notice?: string | null;
    } = await res.json();
    set({
      error: null,
      figureNotice: body.needs_confirmation
        ? body.confirmation_notice ?? 'Check the figures — dictated amounts are not reliable.'
        : null,
    });
    return (body.text ?? '').trim();
  } catch (e) {
    set({ error: e instanceof Error ? e.message : 'Transcription failed.' });
    return '';
  }
}

export const useMicStore = create<MicStore>((set, get) => ({
  status: 'idle',
  mode: 'push',
  level: 0,
  hearingVoice: false,
  unavailableReason: null,
  error: null,
  figureNotice: null,

  checkAvailability: async () => {
    if (!micSupported()) {
      set({ unavailableReason: 'This browser cannot record audio.' });
      return;
    }
    try {
      const res = await fetch(`${API}/voice/stt/health`);
      if (!res.ok) {
        set({ unavailableReason: `Speech recognition is unavailable (${res.status}).` });
        return;
      }
      const body: { available?: boolean; reason?: string } = await res.json();
      set({
        unavailableReason: body.available
          ? null
          : body.reason ?? 'Speech recognition is unavailable.',
      });
    } catch (e) {
      set({
        unavailableReason:
          e instanceof Error ? e.message : 'Could not reach Zaram to ask about listening.',
      });
    }
  },

  start: async () => {
    if (get().status !== 'idle') return;
    if (!micSupported()) {
      set({ error: 'This browser cannot record audio.' });
      return;
    }

    // The notice describes the previous transcript, so it clears here rather
    // than on send — leaving it up would attach a warning about an old amount
    // to a new sentence.
    set({ status: 'requesting', mode: 'push', error: null, figureNotice: null });
    try {
      stream = await navigator.mediaDevices.getUserMedia(AUDIO_CONSTRAINTS);
    } catch (e) {
      // Almost always the permission prompt being declined. Named as the user's
      // own decision rather than as a fault, because it was one.
      teardown();
      set({
        status: 'idle',
        error:
          e instanceof Error && e.name === 'NotAllowedError'
            ? 'Zaram was not given access to the microphone.'
            : e instanceof Error
              ? e.message
              : 'The microphone could not be opened.',
      });
      return;
    }

    recorder = armRecorder();
    recorder?.start();
    set({ status: 'recording' });
  },

  stop: async () => {
    if (get().status !== 'recording' || !recorder) {
      teardown();
      set({ status: 'idle', mode: 'push', level: 0, hearingVoice: false });
      return '';
    }

    const active = recorder;
    const type = active.mimeType || 'audio/webm';
    set({ status: 'transcribing' });

    const blob = await finishRecording(active);
    teardown();

    const text = await transcribe(blob, type, set);
    set({ status: 'idle', mode: 'push', level: 0, hearingVoice: false });
    return text;
  },

  startLatched: async (onUtterance) => {
    if (get().status !== 'idle') return;
    if (!micSupported() || typeof AudioContext === 'undefined') {
      set({ error: 'This browser cannot listen continuously.' });
      return;
    }

    set({ status: 'requesting', mode: 'latched', error: null, figureNotice: null });
    try {
      stream = await navigator.mediaDevices.getUserMedia(AUDIO_CONSTRAINTS);
    } catch (e) {
      teardown();
      set({
        status: 'idle',
        mode: 'push',
        error:
          e instanceof Error && e.name === 'NotAllowedError'
            ? 'Zaram was not given access to the microphone.'
            : e instanceof Error
              ? e.message
              : 'The microphone could not be opened.',
      });
      return;
    }

    latchGeneration += 1;
    const mine = latchGeneration;
    deliver = onUtterance;
    detector = new VoiceActivityDetector();

    audioContext = new AudioContext();
    analyser = audioContext.createAnalyser();
    // 1024 samples at 48 kHz is ~21 ms of audio per reading — comfortably
    // shorter than the interval, so consecutive readings describe different
    // moments rather than overlapping windows of the same one.
    analyser.fftSize = 1024;
    audioContext.createMediaStreamSource(stream).connect(analyser);
    const samples = new Float32Array(analyser.fftSize);

    // `recording` the whole time it is latched, and that is the honest answer:
    // the microphone is open and the browser's indicator is lit. Whether a
    // recorder happens to be capturing this half-second is an implementation
    // detail the user should not have to track, and showing `idle` between
    // sentences would say the microphone was closed when it is not.
    set({ status: 'recording', level: 0, hearingVoice: false });

    levelTimer = setInterval(() => {
      if (mine !== latchGeneration || !analyser || !detector) return;
      analyser.getFloatTimeDomainData(samples);
      const rms = rmsOf(samples);

      // Zaram's own voice, read from the store each tick rather than
      // remembered: it starts and stops on its own schedule, and a value
      // captured when the mode was entered would be stale for the whole
      // conversation.
      const zaramSpeaking = useSpeechStore.getState().audio !== null;
      const event = detector.push(rms, performance.now(), zaramSpeaking);
      set({ level: rms, hearingVoice: detector.isSpeaking });

      if (event === 'onset') {
        // **Barge-in, and this is the moment the feature exists for.** Zaram is
        // talking, the user starts talking, and Zaram stops — rather than the
        // two of them speaking over each other until the reply runs out.
        // `bargeIn` is cheap when nothing is playing, so it is fired on every
        // onset without asking first, which is what `speechStore` asks callers
        // to do.
        useSpeechStore.getState().bargeIn();
        recorder = armRecorder();
        recorder?.start();
        return;
      }

      if (event === 'end' && recorder) {
        const active = recorder;
        recorder = null;
        const type = active.mimeType || 'audio/webm';
        void (async () => {
          const blob = await finishRecording(active);
          // Transcribing does not stop the listening: the next sentence can
          // begin while this one is still being recognised, which is what makes
          // it a conversation rather than a walkie-talkie. `status` therefore
          // stays `recording` rather than flicking to `transcribing` — the
          // microphone genuinely is still open.
          const text = await transcribe(blob, type, set);
          // The generation check is the whole reason it exists: a transcript
          // that lands after the user has left the mode must not appear in
          // their composer.
          if (text && mine === latchGeneration && deliver) deliver(text);
        })();
      }
    }, LEVEL_INTERVAL_MS);
  },

  stopLatched: () => {
    latchGeneration += 1;
    teardown();
    set({ status: 'idle', mode: 'push', level: 0, hearingVoice: false });
  },

  cancel: () => {
    latchGeneration += 1;
    teardown();
    set({ status: 'idle', mode: 'push', level: 0, hearingVoice: false });
  },
}));
