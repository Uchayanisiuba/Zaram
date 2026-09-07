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

/** An opening code fence in the reply being written. */
const OPENS_A_CODE_BLOCK = /(^|\n)\s*```/;

/**
 * `coding` when the work in hand is code, otherwise whatever chat alone says.
 *
 * **Derived from what the system is doing, never from where it routed.** That
 * distinction is the whole reason `local` and `cloud` were removed from this
 * vocabulary on 13 August: a face that reports routing is read as a someone,
 * and "she used the cloud" is the projection the embodiment rule exists to
 * prevent. "A coding model answered" is a routing fact and is *not* what this
 * reads. Two things that are activity are:
 *
 * - **the code tools ran.** A call to the `code` server is Zaram working on a
 *   repository, whatever model was asked.
 * - **the reply is writing code.** An opened fence in the text so far is the
 *   literal thing the maintainer asked to see embodied — Zaram writing code.
 *
 * Either is enough. The fence check runs on the accumulated reply rather than
 * per token, for the reason every other rule in this codebase does: a fence
 * arrives split across tokens, and a per-token test would never see one.
 *
 * Sticky for the rest of the reply, deliberately. A block that closes while
 * more prose follows has not stopped the exchange being a coding exchange, and
 * a state that flickered between two poses mid-answer would read as a fault.
 */
export function codingActivity(
  isStreaming: boolean,
  replySoFar: string,
  toolServers: readonly string[] = [],
): 'coding' | 'thinking' | 'idle' {
  // The base answer first, so "streaming means thinking, otherwise idle" is
  // stated in exactly one place and this function only ever narrows it.
  const base = chatActivity(isStreaming);
  if (base === 'idle') return base;
  if (toolServers.includes('code')) return 'coding';
  return OPENS_A_CODE_BLOCK.test(replySoFar ?? '') ? 'coding' : base;
}
