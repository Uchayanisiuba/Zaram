/**
 * Chat's half of the orb's state, as pure rules.
 *
 * **`preserveSpeaking` lived here until 12 September 2026 and was removed on
 * purpose.** It guarded one field written by two owners — chat and speech —
 * by refusing every chat state while a clip played. That fixed the mouth never
 * opening (19 August) and caused the next report: a fence opening mid-sentence
 * could not turn the orb to `coding`, and speech standing down wrote `idle`
 * over a reply still streaming. The orb store now holds `activity` and
 * `speaking` as separate fields with one owner each and composes them — see
 * `composeOrbState` — so there is nothing left here to guard.
 */


/** What chat activity alone would say. Sticky rules live in `codingActivity`. */
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
 * - **the code tools were put in front of the model.** Added 12 September
 *   2026, for the buffered case: a reply that may call a tool is held back
 *   until it finishes, so no fence and no call reaches the screen while it
 *   runs, and the orb sat on `thinking` for the whole of a coding run. The
 *   offer is system state — the engine chose to hand the model a repository
 *   — and it is the only fact available until the buffer lands.
 *
 * Any is enough. The fence check runs on the accumulated reply rather than
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
  offeredServers: readonly string[] = [],
): 'coding' | 'thinking' | 'idle' {
  // The base answer first, so "streaming means thinking, otherwise idle" is
  // stated in exactly one place and this function only ever narrows it.
  const base = chatActivity(isStreaming);
  if (base === 'idle') return base;
  if (toolServers.includes('code') || offeredServers.includes('code')) return 'coding';
  return OPENS_A_CODE_BLOCK.test(replySoFar ?? '') ? 'coding' : base;
}

/** The servers named by the "tools" notices of the reply in flight. */
export function offeredServers(notices: readonly { kind: string; servers?: string[] }[]): string[] {
  const out = new Set<string>();
  for (const n of notices) {
    if (n.kind !== 'tools') continue;
    for (const s of n.servers ?? []) out.add(s);
  }
  return [...out];
}
