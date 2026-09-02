import type { EmbodimentState } from '@/hooks/useEmbodimentState'

/**
 * Which body clip plays for which system state, and how a variant is chosen.
 *
 * The clips are authored per state with several variants each, so the avatar
 * does not visibly loop the same ten seconds all afternoon. Two rules govern
 * that variation and they pull in opposite directions:
 *
 * **Variants must differ in performance, never in silhouette.** Every clip for
 * a state settles into the same read. If two `thinking` clips landed in
 * visibly different poses the state would stop being learnable, and legibility
 * is the entire job — `docs/EMBODIMENT-SPIKE.md` is explicit that this is a
 * status indicator rather than a character.
 *
 * **Selection is a shuffle bag, not `Math.random()`.** This is the
 * counterintuitive half. True random produces runs — the same clip twice or
 * three times over, which is *precisely* the repetition the variants exist to
 * hide, and it happens often enough to be noticed. Exhausting the set before
 * repeating, and refusing a repeat across the reshuffle seam, makes three
 * clips feel more varied than six drawn independently.
 */

export type ClipRole = 'loop' | 'in' | 'hold'

export interface ClipEntry {
  /** File under `/avatars/animations/`. */
  file: string
  /** Which system state this clip embodies. */
  state: EmbodimentState
  /** `loop` today for every clip; `in`/`hold` exists for the transition split
   *  the animation brief describes, which the current exports do not yet use. */
  role?: ClipRole
}

export interface AnimationManifest {
  version: string
  clips: ClipEntry[]
}

/**
 * Draws from a set without repeating until the set is exhausted.
 *
 * The seam check is the part that matters and the part usually left out: a bag
 * that reshuffles freely can hand out the same item as the last of one round
 * and the first of the next, which is the one sequence a viewer reliably
 * notices. Swapping it with the second element costs nothing and removes the
 * only visible failure mode.
 *
 * A single-item bag returns that item forever, which is correct rather than a
 * degenerate case — a state with one clip has nothing to vary.
 */
export class ShuffleBag<T> {
  private readonly items: readonly T[]
  private queue: T[] = []
  private last: T | undefined

  constructor(items: readonly T[], private readonly rng: () => number = Math.random) {
    this.items = items.slice()
  }

  get size(): number {
    return this.items.length
  }

  next(): T | undefined {
    if (this.items.length === 0) return undefined
    if (this.queue.length === 0) this.refill()
    const drawn = this.queue.pop() as T
    this.last = drawn
    return drawn
  }

  private refill(): void {
    const q = this.items.slice()
    for (let i = q.length - 1; i > 0; i--) {
      const j = Math.floor(this.rng() * (i + 1))
      ;[q[i], q[j]] = [q[j], q[i]]
    }
    // `pop` draws from the end, so the end is the next item out.
    if (q.length > 1 && q[q.length - 1] === this.last) {
      ;[q[q.length - 1], q[q.length - 2]] = [q[q.length - 2], q[q.length - 1]]
    }
    this.queue = q
  }
}

/** Group a manifest's clips by the state they embody. */
export function clipsByState(manifest: AnimationManifest): Map<EmbodimentState, ClipEntry[]> {
  const out = new Map<EmbodimentState, ClipEntry[]>()
  for (const clip of manifest.clips) {
    const list = out.get(clip.state)
    if (list) list.push(clip)
    else out.set(clip.state, [clip])
  }
  return out
}

/**
 * The clip name a loaded file is addressed by.
 *
 * An FBX carries its own internal take name — Maya writes `Take 001` into every
 * one of them regardless of what the file is called — so the take name is
 * useless as an identity. The filename is the only thing that distinguishes
 * `Idle_01` from `Talk_3`, which is why the manifest keys on it and why the
 * exports were asked to be named after their clips.
 */
export function clipNameOf(entry: ClipEntry): string {
  return entry.file.replace(/\.[^.]+$/, '')
}

/**
 * Which states have no clip at all.
 *
 * Reported rather than thrown. A state with no body animation still has a rim
 * light, a face and a legible label, so it degrades to the pose it is already
 * holding — but silence about it is how a missing export survives to a release,
 * and this codebase has a long record of exactly that.
 */
export function statesWithoutClips(
  manifest: AnimationManifest,
  all: readonly EmbodimentState[],
): EmbodimentState[] {
  const have = clipsByState(manifest)
  return all.filter((s) => !have.has(s))
}
