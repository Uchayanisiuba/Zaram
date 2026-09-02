/**
 * Clip selection, tested for the property the feature exists to deliver.
 *
 * The variants were authored so the avatar does not visibly loop the same ten
 * seconds all afternoon. `Math.random()` defeats that on its own: independent
 * draws produce runs, and a clip playing twice in a row is exactly the
 * repetition the variants were made to hide. So the interesting assertions here
 * are about *sequences*, not about single calls.
 */
import { describe, it, expect } from 'vitest'
import shipped from '../../public/avatars/animations/animations.json'
import {
  ShuffleBag, clipsByState, clipNameOf, statesWithoutClips,
  type AnimationManifest,
} from './animationSet'
import type { EmbodimentState } from '@/hooks/useEmbodimentState'

const ALL: EmbodimentState[] = ['idle', 'thinking', 'listening', 'speaking', 'swapping']

describe('ShuffleBag', () => {
  it('exhausts the set before repeating anything', () => {
    const bag = new ShuffleBag(['a', 'b', 'c'])
    const round = [bag.next(), bag.next(), bag.next()]
    expect([...round].sort()).toEqual(['a', 'b', 'c'])
  })

  it('never draws the same clip twice in a row, including across the reshuffle', () => {
    // The seam is the case a naive bag gets wrong: last of one round and first
    // of the next can be the same item, which is the one sequence a viewer
    // reliably notices. 300 draws over 3 items crosses the seam ~100 times.
    const bag = new ShuffleBag(['a', 'b', 'c'])
    let previous = bag.next()
    for (let i = 0; i < 300; i++) {
      const drawn = bag.next()
      expect(drawn).not.toBe(previous)
      previous = drawn
    }
  })

  it('returns the only clip forever when a state has one', () => {
    // Correct rather than degenerate: a state with one export has nothing to
    // vary, and refusing a repeat there would mean returning nothing.
    const bag = new ShuffleBag(['only'])
    expect([bag.next(), bag.next(), bag.next()]).toEqual(['only', 'only', 'only'])
  })

  it('returns undefined for an empty set rather than throwing', () => {
    expect(new ShuffleBag<string>([]).next()).toBeUndefined()
  })

  it('uses every clip roughly evenly', () => {
    const counts: Record<string, number> = { a: 0, b: 0, c: 0, d: 0 }
    const bag = new ShuffleBag(['a', 'b', 'c', 'd'])
    for (let i = 0; i < 400; i++) counts[bag.next() as string]++
    for (const n of Object.values(counts)) expect(n).toBe(100)
  })

  it('does not mutate the caller’s array', () => {
    const items = ['a', 'b']
    const bag = new ShuffleBag(items)
    bag.next(); bag.next(); bag.next()
    expect(items).toEqual(['a', 'b'])
  })
})

describe('clipNameOf', () => {
  it('names a clip by its file, because the take name is worthless', () => {
    // Maya writes `Take 001` into every FBX it exports regardless of what the
    // file is called, so the internal take name cannot distinguish Idle_01
    // from Talk_3. The filename is the only identity these clips have.
    expect(clipNameOf({ file: 'idle_a.fbx', state: 'idle' })).toBe('idle_a')
    expect(clipNameOf({ file: 'thinking_in_tilt.fbx', state: 'thinking' })).toBe('thinking_in_tilt')
  })
})

describe('clipsByState / statesWithoutClips', () => {
  const manifest: AnimationManifest = {
    version: 't',
    clips: [
      { file: 'idle_a.fbx', state: 'idle' },
      { file: 'idle_b.fbx', state: 'idle' },
      { file: 'thinking.fbx', state: 'thinking' },
    ],
  }

  it('groups every clip under its state', () => {
    const byState = clipsByState(manifest)
    expect(byState.get('idle')?.map(clipNameOf)).toEqual(['idle_a', 'idle_b'])
    expect(byState.get('thinking')).toHaveLength(1)
  })

  it('names the states with no clip at all', () => {
    expect(statesWithoutClips(manifest, ALL).sort()).toEqual(['listening', 'speaking', 'swapping'])
  })
})

describe('the shipped animation manifest', () => {
  const manifest = shipped as AnimationManifest

  it('names only states the embodiment actually has', () => {
    // A clip filed under a state that does not exist can never play, and
    // nothing at runtime would say so.
    for (const clip of manifest.clips) expect(ALL).toContain(clip.state)
  })

  it('gives every state it claims at least one clip', () => {
    for (const [, list] of clipsByState(manifest)) expect(list.length).toBeGreaterThan(0)
  })

  it('records which states are still missing body animation', () => {
    // Not a failure — a state with no clip holds its current pose and keeps its
    // rim light and face. This asserts the *known* gap so that filling it is a
    // deliberate edit here rather than something nobody notices either way.
    //
    // It was four states. Six clips had been exported against an Advanced
    // Skeleton rig (`Shoulder_L`, `Elbow_L`) rather than the character's own
    // `Robot_All_01`, so nothing bound them by name;
    // `avatar-source/retarget_advanced_skeleton.py` maps the two conventions and
    // bakes them onto the character's armature, which left only `swapping`.
    //
    // **`swapping` is a deliberate omission rather than a missing export.** It
    // is the one state where nothing is resident and no work is happening, and
    // `CLAUDE.md` is explicit that it should read as the character receding —
    // holding still while the glow dims says that better than any clip would.
    expect(statesWithoutClips(manifest, ALL).sort()).toEqual(['swapping'])
  })
})
