import { Volume2, Square } from 'lucide-react';
import { useEmbodimentStore } from '@/stores/embodimentStore';
import { useSpeechStore } from '@/stores/speechStore';

/**
 * "Speak this reply" — the *asked* half of "orb, silent unless asked".
 *
 * `CLAUDE.md` says speech follows the renderer: the avatar speaks, the orb is
 * **silent unless asked**. `chatStore` implements the first clause and nothing
 * implemented the second, so on the landing default — which is the orb — every
 * reply was silent and there was no way to hear one and nothing on screen
 * saying why. A tester who has just installed the voice extra concludes it is
 * broken, and they are not being unreasonable: from where they sit, it is.
 *
 * This is the fix rather than a settings toggle, because a toggle would be a
 * second control for a choice the user already made by picking a face — the
 * "never make the user choose in advance" rule. Asking for one reply is not a
 * preference, it is an action.
 *
 * **Hidden while the avatar is showing.** There the reply already speaks by
 * itself, and a button offering to do what just happened reads as a bug.
 */
export default function SpeakButton({ text }: { text: string }) {
  const renderer = useEmbodimentStore((s) => s.renderer);
  // `audio` is the store's own record of what is playing — there is no separate
  // `speaking` flag, and adding one would be a second place for the same truth.
  const audio = useSpeechStore((s) => s.audio);
  const speak = useSpeechStore((s) => s.speak);
  const stop = useSpeechStore((s) => s.stop);

  if (renderer !== 'orb' || !text.trim()) return null;

  const active = audio !== null;

  return (
    <button
      type="button"
      onClick={() => (active ? stop() : void speak(text))}
      // The label carries the state, because the icon alone does not: a speaker
      // and a stop square are not self-evident to a screen reader, and this is
      // the one control in the conversation whose whole purpose is audio.
      aria-label={active ? 'Stop speaking this reply' : 'Speak this reply aloud'}
      title={active ? 'Stop' : 'Speak this reply'}
      className="mt-1.5 inline-flex items-center gap-1 rounded px-1 -mx-1 text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
    >
      {active ? <Square size={9} aria-hidden /> : <Volume2 size={10} aria-hidden />}
      <span>{active ? 'Stop' : 'Speak'}</span>
    </button>
  );
}
