/**
 * The reply being written, typed out at a steady cadence.
 *
 * **This component exists to keep the typewriter out of `ChatSurface`.**
 * `useTypedText` advances a piece of React state on every animation frame for
 * as long as a reply streams. Until 12 September 2026 that hook lived at the
 * top of `ChatSurface` — a 1,400-line component holding the whole transcript
 * — so every reveal frame re-rendered the surface and, through it, re-parsed
 * every message in the conversation. Measured symptom: the interface hung
 * while code streamed, and the longer the conversation the worse it got.
 *
 * Here the frame-rate state is owned by a component that renders one thing.
 * `ChatSurface` still re-renders per *token* (it subscribes to
 * `streamingText` for the scroll and the orb), which is tens of times a
 * second rather than sixty, and with `MessageBody` memoised the transcript
 * above costs nothing on either.
 *
 * `streaming` is passed through to `MessageBody`, which skips syntax
 * highlighting while the text is still changing. Both props are read from the
 * store by the caller so this stays a pure function of its inputs.
 */
import { useTypedText } from '@/hooks/useTypedText';
import MessageBody from './MessageBody';

export default function StreamingReply({ text, done }: { text: string; done: boolean }) {
  const typed = useTypedText(text, done);
  return <MessageBody text={typed} streaming={!done} />;
}
