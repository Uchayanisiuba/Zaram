import { useCallback, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Mic, Square } from 'lucide-react';
import { useMicStore } from '@/stores/micStore';
import { useSpeechStore } from '@/stores/speechStore';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';

/**
 * Speak instead of typing. Local transcription, on this machine.
 *
 * **Two gestures, and the second one was argued against here before it was
 * asked for.** This file used to carry a flat refusal of hold-to-talk, on the
 * grounds that holding is a *pointer* gesture — a keyboard or screen-reader
 * user activating a button gets one event, not a down and an up — and that a
 * control which is both asks the user to discover which one they performed.
 *
 * That reasoning was right about hold-*only* and wrong as a reason to have one
 * gesture. What makes two safe is that they are not alternatives:
 *
 * * **Click** is unchanged. Press to start, press again to stop and transcribe.
 *   Nothing anybody relies on moved, and everything the control could do
 *   before, it still does with one activation.
 * * **Hold** *adds* a mode, and it is additive in the same sense a manner is
 *   additive to identity: it cannot take anything away, and the thing it opens
 *   is closed by an ordinary click.
 *
 * The accessibility objection is answered rather than accepted, because the
 * answer is cheap: **Alt-click reaches the same mode**, which a keyboard user
 * gets for free since a modifier held during Enter travels to the click event,
 * and the accessible name says both routes out loud rather than leaving the
 * gesture to be discovered. A control whose second gesture is undiscoverable is
 * the real failure the old note was pointing at.
 *
 * **What latched mode is.** The microphone stays open across turns, each
 * utterance is cut on the pause after it and transcribed on its own, and — the
 * point of it — Zaram's voice stops the moment the user starts talking.
 * `micStore` and `lib/voiceActivity.ts` hold that machinery; this file is the
 * gesture and the indication.
 *
 * The transcript goes to the caller rather than into the composer directly. It
 * lands in the input as editable text and is never sent on the user's behalf:
 * a recogniser that mishears and then submits has spoken for them — and in a
 * mode designed to be left running for a long conversation, it gets far more
 * chances to.
 */

/**
 * How long the button has to be held before it latches, in ms.
 *
 * Long enough not to fire on an ordinary slow click, short enough that somebody
 * doing it deliberately is not left wondering whether it worked. The ring
 * appearing is the confirmation, so this is the whole delay the user perceives.
 */
const HOLD_MS = 450;

export default function MicButton({
  onTranscript,
  disabled = false,
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}) {
  const reduced = useIsReducedMotion();
  const status = useMicStore((s) => s.status);
  const mode = useMicStore((s) => s.mode);
  const level = useMicStore((s) => s.level);
  const hearingVoice = useMicStore((s) => s.hearingVoice);
  const unavailableReason = useMicStore((s) => s.unavailableReason);
  const start = useMicStore((s) => s.start);
  const stop = useMicStore((s) => s.stop);
  const cancel = useMicStore((s) => s.cancel);
  const startLatched = useMicStore((s) => s.startLatched);
  const stopLatched = useMicStore((s) => s.stopLatched);
  const checkAvailability = useMicStore((s) => s.checkAvailability);

  /** The pending hold timer, and whether it fired.
   *
   *  `consumed` is what stops a hold also being a click: a press that latched
   *  must not then toggle the mode straight back off when the finger lifts,
   *  which is exactly what happens if the click handler runs unguarded. */
  const holdTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const consumed = useRef(false);

  useEffect(() => {
    void checkAvailability();
  }, [checkAvailability]);

  // Leaving the surface mid-recording must not leave the microphone open. The
  // browser's recording indicator is the user's only sight of this.
  useEffect(() => () => cancel(), [cancel]);

  useEffect(
    () => () => {
      if (holdTimer.current) clearTimeout(holdTimer.current);
    },
    [],
  );

  const latched = mode === 'latched' && status !== 'idle';
  const recording = status === 'recording' && !latched;
  const busy = status === 'transcribing' || status === 'requesting';
  const blocked = unavailableReason !== null;

  const enterLatched = useCallback(() => {
    // Barge-in on the way in as well as on every onset once inside. Entering
    // the mode is itself an interruption: nobody opens a conversation
    // microphone in order to keep listening to the last answer.
    useSpeechStore.getState().bargeIn();
    void startLatched(onTranscript);
  }, [startLatched, onTranscript]);

  const beginHold = () => {
    if (disabled || blocked || busy || latched || recording) return;
    consumed.current = false;
    holdTimer.current = setTimeout(() => {
      holdTimer.current = null;
      consumed.current = true;
      enterLatched();
    }, HOLD_MS);
  };

  const endHold = () => {
    if (holdTimer.current) {
      clearTimeout(holdTimer.current);
      holdTimer.current = null;
    }
  };

  const handleClick = async (event: { altKey?: boolean; metaKey?: boolean }) => {
    // The press that latched already did its work; the release is not a second
    // instruction.
    if (consumed.current) {
      consumed.current = false;
      return;
    }
    if (latched) {
      stopLatched();
      return;
    }
    // The keyboard's route into the same mode. A modifier held while Enter is
    // pressed travels to the click, so this costs a keyboard user nothing that
    // a pointer user is not also paying.
    if ((event.altKey || event.metaKey) && !recording) {
      enterLatched();
      return;
    }
    if (recording) {
      const text = await stop();
      if (text) onTranscript(text);
      return;
    }
    // Barge-in by microphone, and here it is a correctness requirement rather
    // than a courtesy: the microphone would otherwise record Zaram's own voice
    // coming out of the speakers and transcribe it back as if the user had said
    // it. Stopping first is the difference between listening and a feedback
    // loop.
    useSpeechStore.getState().bargeIn();
    await start();
  };

  const label = blocked
    ? `Voice input unavailable — ${unavailableReason}`
    : latched
      ? hearingVoice
        ? 'Listening — hearing you. Click to stop'
        : 'Listening for a long conversation. Click to stop'
      : recording
        ? 'Stop recording and transcribe'
        : status === 'transcribing'
          ? 'Transcribing'
          : // The second gesture is named rather than left to be discovered.
            // This is the whole answer to the accessibility objection in the
            // note above: a control with a hidden mode has one mode.
            'Record a message — hold down for a long conversation';

  return (
    <span className="relative inline-flex">
      {/* The indication that the mode changed, and it is deliberately a
          *shape* rather than a new colour.

          Cyan is what this product already means by "this stayed on your
          machine" — the orb, the citation chips, and the recording square
          below. Latched audio is just as local, so inventing a second hue for
          it would either say something untrue or teach the user a colour that
          means nothing. The ring says "still open" by existing; the level says
          "and still hearing you" by moving. */}
      {latched && (
        <motion.span
          aria-hidden
          className="absolute inset-0 rounded-lg pointer-events-none"
          style={{ border: '1px solid var(--color-cyan)' }}
          animate={
            reduced
              ? { opacity: 0.9 }
              : {
                  // Driven by what the microphone actually hears, so a latched
                  // microphone that has gone deaf looks different from one
                  // waiting politely. A ring animating on a timer would look
                  // identical either way, which is the invented-value failure
                  // wearing an animation.
                  opacity: 0.45 + Math.min(level * 6, 0.55),
                  scale: 1 + Math.min(level * 1.2, 0.12),
                }
          }
          transition={{ duration: 0.12, ease: 'linear' }}
        />
      )}
      <motion.button
        type="button"
        onPointerDown={beginHold}
        onPointerUp={endHold}
        onPointerLeave={endHold}
        onPointerCancel={endHold}
        onClick={handleClick}
        disabled={disabled || busy || blocked}
        aria-label={label}
        title={label}
        // The one piece of state a screen reader would otherwise miss: the icon
        // changes, and nothing else announces that Zaram is now listening.
        aria-pressed={recording || latched}
        // Positioned by its parent, not by itself.
        //
        // This used to carry `absolute right-9 top-1/2 -translate-y-1/2`, while
        // the send button next to it carried `absolute right-2`. Two independent
        // hand-computed offsets for two controls that must not touch: at
        // `p-1.5` around a 16px icon each button is 28px wide, so `right-2` spans
        // 8–36px and `right-9` spans 36–64px — adjacent, with a gap of exactly
        // zero. Then `whileHover={{ scale: 1.05 }}` grew whichever one the mouse
        // was over into its neighbour, which is why the overlap only appeared on
        // hover and looked intermittent.
        //
        // A flex row with a real gap removes the arithmetic rather than
        // correcting it. Nothing here needs to know how wide the other control
        // is.
        className="p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors"
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
      >
        {recording ? (
          <motion.span
            className="block"
            // Recording is the one state where the control has to be unmistakable
            // from across the room. Cyan, because the audio stayed on this
            // machine, and that is what cyan already means on the orb and in
            // citation chips.
            animate={reduced ? undefined : { opacity: [1, 0.45, 1] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
          >
            <Square size={14} fill="currentColor" style={{ color: 'var(--color-cyan)' }} />
          </motion.span>
        ) : (
          <Mic
            size={16}
            className="text-slate-300"
            // Latched keeps the microphone icon rather than switching to the
            // stop square. The square means "one recording is running and this
            // ends it"; latched has no single recording to end, and borrowing
            // the symbol would say the wrong thing about what a click does.
            style={latched || busy ? { color: 'var(--color-cyan)' } : undefined}
          />
        )}
      </motion.button>
    </span>
  );
}
