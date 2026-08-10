import { create } from 'zustand';

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

/** Release the microphone and forget the recording. Always safe to call. */
function teardown(): void {
  if (recorder && recorder.state !== 'inactive') {
    try {
      recorder.stop();
    } catch {
      // Already stopping. Nothing to do; the tracks below are what matter.
    }
  }
  stream?.getTracks().forEach((track) => track.stop());
  recorder = null;
  stream = null;
  chunks = [];
}

interface MicStore {
  status: MicStatus;
  /** Why Zaram cannot listen, as the backend phrased it. Written for the user —
   *  it names the install and its size, or the blocked download and its size —
   *  so it is rendered as-is rather than replaced with "unavailable". */
  unavailableReason: string | null;
  /** A failure of this attempt, as distinct from the capability being absent.
   *  A denied microphone permission is not a missing extra, and telling someone
   *  to install 81 MB when they clicked Block would be a wrong diagnosis. */
  error: string | null;

  /** Ask the backend whether it can listen. Local call; no egress. */
  checkAvailability: () => Promise<void>;
  start: () => Promise<void>;
  /** Stop, transcribe, and return what was heard. Empty string when nothing
   *  was. The caller decides where the text goes — this store does not know
   *  about the composer. */
  stop: () => Promise<string>;
  /** Throw the recording away and release the microphone. */
  cancel: () => void;
}

export const useMicStore = create<MicStore>((set, get) => ({
  status: 'idle',
  unavailableReason: null,
  error: null,

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

    set({ status: 'requesting', error: null });
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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

    const mimeType = pickMimeType();
    chunks = [];
    recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.start();
    set({ status: 'recording' });
  },

  stop: async () => {
    if (get().status !== 'recording' || !recorder) {
      teardown();
      set({ status: 'idle' });
      return '';
    }

    const active = recorder;
    const type = active.mimeType || 'audio/webm';
    set({ status: 'transcribing' });

    const blob = await new Promise<Blob>((resolve) => {
      // `stop()` flushes a final `dataavailable` before `stop` fires, so the
      // blob has to be assembled in the stop handler. Assembling it beside the
      // call would drop the last chunk — the end of the sentence.
      active.onstop = () => resolve(new Blob(chunks, { type }));
      try {
        active.stop();
      } catch {
        resolve(new Blob(chunks, { type }));
      }
    });

    teardown();

    if (blob.size === 0) {
      set({ status: 'idle' });
      return '';
    }

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
          // The capability is missing, not this attempt. Recorded where the
          // button reads it, so the control disables itself with the reason
          // rather than failing again on the next press.
          set({ status: 'idle', unavailableReason: detail ?? 'Zaram cannot listen yet.' });
        } else {
          set({ status: 'idle', error: detail ?? `Transcription failed (${res.status}).` });
        }
        return '';
      }

      const body: { text?: string } = await res.json();
      set({ status: 'idle', error: null });
      return (body.text ?? '').trim();
    } catch (e) {
      set({
        status: 'idle',
        error: e instanceof Error ? e.message : 'Transcription failed.',
      });
      return '';
    }
  },

  cancel: () => {
    teardown();
    set({ status: 'idle' });
  },
}));
