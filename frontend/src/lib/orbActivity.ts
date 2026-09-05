import type { OrbState } from '@/stores/orbStore';
import type { OrbActivity } from '@/stores/systemStore';

/**
 * Speech owns `speaking`; chat activity may not overwrite it.
 *
 * **Two writers, one state, and only one of them was guarding — found 19 August
 * 2026.** `ChatSurface` set `thinking` while a request was in flight and `idle`
 * the moment it finished. `speechStore` sets `speaking` while a clip plays, and
 * already refused to stand down over anybody else's state:
 * *"only stand down if nothing else has taken the state in the meantime"*. That
 * asymmetry is the whole bug. Speech starts on the first sentence that will not
 * change again and outlives the stream **by design** — `CLAUDE.md` requires
 * exactly that — so the `idle` written when generation ended landed on top of
 * `speaking` every time, on every reply.
 *
 * **Nothing looked broken, which is why it survived.** The rim light is the
 * same cyan for `thinking` and for `speaking`, so the only renderer that could
 * show the difference was the avatar's mouth, and a mouth that never opens
 * reads as "lip sync was never finished" rather than as a state bug. Measured
 * in the browser before the fix: audio playing, `currentTime` advancing 0 →
 * 8.1s, `paused` false throughout, and the mouth shut in all 40 frames.
 *
 * A rule about a shared store, expressed as a function so a test can assert it
 * rather than a component having to be rendered to find out.
 */
export function preserveSpeaking<T extends OrbState | OrbActivity>(current: T, next: T): T {
  return current === 'speaking' ? current : next;
}

/** What chat activity alone would say. The other half of the sentence above. */
export function chatActivity(isStreaming: boolean): 'thinking' | 'idle' {
  return isStreaming ? 'thinking' : 'idle';
}
