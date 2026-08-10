import { useEffect } from 'react';
import { motion } from 'framer-motion';
import { Mic, Square } from 'lucide-react';
import { useMicStore } from '@/stores/micStore';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';

/**
 * Speak instead of typing. Local transcription, on this machine.
 *
 * **Press to start, press again to stop — not hold-to-talk.** Holding is the
 * familiar gesture and it is a pointer gesture: a keyboard or screen-reader user
 * activating a button gets one event, not a down and an up, so a hold-only
 * control is unusable to them and a control that is *both* asks the user to
 * discover which one they performed. One behaviour, available to everyone, is
 * the trade — and it is the same reason the left rail's collapsed buttons got
 * real accessible names.
 *
 * The transcript goes to the caller rather than into the composer directly. It
 * lands in the input as editable text and is never sent on the user's behalf:
 * a recogniser that mishears and then submits has spoken for them.
 */
export default function MicButton({
  onTranscript,
  disabled = false,
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}) {
  const reduced = useIsReducedMotion();
  const status = useMicStore((s) => s.status);
  const unavailableReason = useMicStore((s) => s.unavailableReason);
  const start = useMicStore((s) => s.start);
  const stop = useMicStore((s) => s.stop);
  const cancel = useMicStore((s) => s.cancel);
  const checkAvailability = useMicStore((s) => s.checkAvailability);

  useEffect(() => {
    void checkAvailability();
  }, [checkAvailability]);

  // Leaving the surface mid-recording must not leave the microphone open. The
  // browser's recording indicator is the user's only sight of this.
  useEffect(() => () => cancel(), [cancel]);

  const recording = status === 'recording';
  const busy = status === 'transcribing' || status === 'requesting';
  const blocked = unavailableReason !== null;

  const handleClick = async () => {
    if (recording) {
      const text = await stop();
      if (text) onTranscript(text);
      return;
    }
    await start();
  };

  const label = blocked
    ? `Voice input unavailable — ${unavailableReason}`
    : recording
      ? 'Stop recording and transcribe'
      : status === 'transcribing'
        ? 'Transcribing'
        : 'Record a message';

  return (
    <motion.button
      type="button"
      onClick={handleClick}
      disabled={disabled || busy || blocked}
      aria-label={label}
      title={label}
      // The one piece of state a screen reader would otherwise miss: the icon
      // changes, and nothing else announces that Zaram is now listening.
      aria-pressed={recording}
      className="absolute right-9 top-1/2 -translate-y-1/2 p-1.5 rounded-lg hover:bg-white/5 disabled:opacity-30 transition-colors"
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
          style={busy ? { color: 'var(--color-cyan)' } : undefined}
        />
      )}
    </motion.button>
  );
}
