/**
 * The two settings that made the avatar look pixelated.
 *
 * Both were wrong in the same way: the code *looked* like it handled the
 * problem. `antialias: true` was set — and confirmed live at `SAMPLES = 4` —
 * but MSAA smooths silhouettes and does nothing for texture sampling inside a
 * surface, which is where aliasing on a face lives. Meanwhile the render buffer
 * was 320x320 on a DPR-1 display and every texture sat at three.js's default
 * anisotropy of **1**, neither of which appears as a setting anyone wrote.
 *
 * They are tested here rather than eyeballed because the avatar asset is being
 * replaced — a humanoid robot with an LED face — and an emissive dot grid
 * aliases harder than skin does, so these have to survive the swap.
 */
import * as THREE from 'three'
import { describe, it, expect } from 'vitest'
import { renderScaleFor, applyTextureFiltering, approachRate } from './VrmAvatar'

describe('renderScaleFor', () => {
  it('supersamples on an ordinary 1x display', () => {
    // The defect, as an assertion. At 1 the whole head renders into 320x320.
    expect(renderScaleFor(1)).toBe(2)
  })

  it('renders natively on a 2x display', () => {
    expect(renderScaleFor(2)).toBe(2)
  })

  it('still caps above 2, which was the original intent and was correct', () => {
    // Deliberately soft on a 3x display: the returns are invisible at 320px
    // and the fragment cost is not. Removing the floor must not remove the cap.
    expect(renderScaleFor(3)).toBe(2)
    expect(renderScaleFor(4)).toBe(2)
  })
})

describe('applyTextureFiltering', () => {
  /** A mesh whose material carries textures under non-standard slot names,
   *  which is the case that matters: VRM materials are MToon. */
  function sceneWithTextures() {
    const root = new THREE.Group()
    const material = new THREE.MeshBasicMaterial()
    material.map = new THREE.Texture()
    // MToon's own slots. A hardcoded list of `map`/`normalMap` would skip
    // these, and the shade map is most of what a cel-shaded face samples.
    ;(material as unknown as Record<string, unknown>).shadeMultiplyTexture = new THREE.Texture()
    ;(material as unknown as Record<string, unknown>).rimMultiplyTexture = new THREE.Texture()

    root.add(new THREE.Mesh(new THREE.BufferGeometry(), material))
    return { root, material }
  }

  it('raises anisotropy on every texture slot, whatever it is called', () => {
    const { root, material } = sceneWithTextures()

    const textures = [
      material.map!,
      (material as unknown as Record<string, THREE.Texture>).shadeMultiplyTexture,
      (material as unknown as Record<string, THREE.Texture>).rimMultiplyTexture,
    ]
    // The default this exists to correct. If three.js ever changes it, this
    // line fails and the premise gets re-read rather than the fix being kept
    // out of habit.
    expect(textures.map((t) => t.anisotropy)).toEqual([1, 1, 1])

    const count = applyTextureFiltering(root, 16)

    expect(count).toBe(3)
    expect(textures.map((t) => t.anisotropy)).toEqual([16, 16, 16])
  })

  it('sets the mipmapped min filter, because anisotropy samples between mips', () => {
    // A texture on NearestFilter has no mipmaps and keeps aliasing however high
    // the anisotropy goes, so raising one without the other is a no-op that
    // reads as a fix.
    const { root, material } = sceneWithTextures()
    material.map!.minFilter = THREE.NearestFilter
    const before = material.map!.version

    applyTextureFiltering(root, 16)

    expect(material.map!.minFilter).toBe(THREE.LinearMipmapLinearFilter)
    expect(material.map!.generateMipmaps).toBe(true)
    // `needsUpdate` is a write-only setter on Texture — reading it gives
    // `undefined`, so asserting on it would have passed nothing. What it
    // actually does is bump `version`, which is what the renderer reads to
    // decide whether to re-upload, so that is what gets asserted.
    expect(material.map!.version).toBeGreaterThan(before)
  })

  it('counts a shared texture once', () => {
    // Two meshes sharing one map is one upload, and reporting it twice would
    // make the diagnostic line in the console overstate the work done.
    const root = new THREE.Group()
    const shared = new THREE.Texture()
    for (let i = 0; i < 2; i++) {
      const material = new THREE.MeshBasicMaterial()
      material.map = shared
      root.add(new THREE.Mesh(new THREE.BufferGeometry(), material))
    }

    expect(applyTextureFiltering(root, 16)).toBe(1)
  })

  it('finds textures held as uniforms, which is how MToon holds them', () => {
    // The case the first version of this function missed, and the reason it
    // reported `textures filtered: 0` against the real avatar while its unit
    // tests passed. MToonMaterial extends ShaderMaterial: `map` and
    // `shadeMultiplyTexture` are accessors on the *prototype* reading
    // `this.uniforms`, so `Object.values(instance)` sees neither.
    const root = new THREE.Group()
    const material = new THREE.ShaderMaterial()
    const base = new THREE.Texture()
    const shade = new THREE.Texture()
    material.uniforms = {
      map: { value: base },
      shadeMultiplyTexture: { value: shade },
      // A non-texture uniform alongside them, so the walk has to discriminate
      // rather than assume every uniform holds a texture.
      shadingShiftFactor: { value: 0.4 },
    }
    root.add(new THREE.Mesh(new THREE.BufferGeometry(), material))

    expect(applyTextureFiltering(root, 16)).toBe(2)
    expect(base.anisotropy).toBe(16)
    expect(shade.anisotropy).toBe(16)
  })

  it('reports zero on a scene with no textures, rather than claiming success', () => {
    const root = new THREE.Group()
    root.add(new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial()))

    expect(applyTextureFiltering(root, 16)).toBe(0)
  })

  it('survives an array material and an object with none', () => {
    const root = new THREE.Group()
    root.add(new THREE.Object3D())
    const material = new THREE.MeshBasicMaterial()
    material.map = new THREE.Texture()
    root.add(new THREE.Mesh(new THREE.BufferGeometry(), [material, new THREE.MeshBasicMaterial()]))

    expect(applyTextureFiltering(root, 8)).toBe(1)
    expect(material.map.anisotropy).toBe(8)
  })
})

/**
 * State changes are transitions now, not cuts.
 *
 * The rim light is the state channel and it was assigned absolutely every
 * frame, so idle-to-thinking swapped slate for cyan between two frames. On a
 * surface briefed as *calm over delight*, an instant colour flip is the one
 * motion that reads as a glitch rather than as a state.
 *
 * The property worth asserting is not "it eases" — that is visible or it is
 * not, and this environment cannot take a screenshot. It is that the easing is
 * **frame-rate independent**, which is invisible on the machine it was tuned on
 * and wrong everywhere else. The lerps already in this file were not: at 144Hz
 * `dt * 3` covers three times the distance per second it covers at 48Hz.
 */
describe('approachRate', () => {
  it('covers the same distance in the same wall-clock time at any refresh rate', () => {
    // A quarter second at three refresh rates. The frame counts have to divide
    // it exactly or the test compares different durations and fails for a
    // reason that has nothing to do with the property — which is what the
    // first version of this did, at 8 frames of 30Hz for 0.267s against 0.25s.
    const remainingAfterQuarterSecond = (hz: number) => {
      const frames = 0.25 * hz
      expect(Number.isInteger(frames)).toBe(true)
      let left = 1
      for (let i = 0; i < frames; i++) left *= 1 - approachRate(1 / hz, 0.22)
      return left
    }

    const at48 = remainingAfterQuarterSecond(48)
    const at60 = remainingAfterQuarterSecond(60)
    const at240 = remainingAfterQuarterSecond(240)

    // Within a percent of each other despite five times the frame count.
    expect(Math.abs(at60 - at240)).toBeLessThan(0.01)
    expect(Math.abs(at60 - at48)).toBeLessThan(0.01)
  })

  it('is what the old frame-tied form was not, and the honest size of that', () => {
    // Written first as "the old form diverges by more than 1% between 60Hz and
    // 240Hz" and it failed at 0.68%. The claim was too strong: `dt * rate` is a
    // first-order approximation of the exponential, so at short frame times the
    // two agree closely. Where it actually breaks is long frames — and it
    // breaks completely rather than gradually.
    const oldForm = (hz: number) => {
      let left = 1
      for (let i = 0; i < 0.25 * hz; i++) left *= 1 - (1 / hz) * 3
      return left
    }
    const newForm = (hz: number) => {
      let left = 1
      for (let i = 0; i < 0.25 * hz; i++) left *= 1 - approachRate(1 / hz, 1 / 3)
      return left
    }

    // The error grows as the frame time grows — that is the whole defect.
    const errorAt20 = Math.abs(oldForm(20) - oldForm(240))
    const errorAt60 = Math.abs(oldForm(60) - oldForm(240))
    expect(errorAt20).toBeGreaterThan(errorAt60)

    // The new form does not have it, at either rate.
    expect(Math.abs(newForm(20) - newForm(240))).toBeLessThan(errorAt20)

    // And past dt = 1/3 the old factor exceeds 1, which is not a small error —
    // the value shoots past its target and comes back.
    expect(0.5 * 3).toBeGreaterThan(1)
    expect(approachRate(0.5, 1 / 3)).toBeLessThanOrEqual(1)
  })

  it('is close to arrived after three time constants', () => {
    // The tuning claim in the comment, asserted: ~95% of the way there.
    let left = 1
    for (let i = 0; i < 60; i++) left *= 1 - approachRate(0.66 / 60, 0.22)
    expect(left).toBeLessThan(0.06)
  })

  it('never overshoots on a long frame', () => {
    // A backgrounded tab returning, or a model finishing a load. The first
    // version of this asserted `toBe(1)` and failed at 0.9999999998 — which
    // was the test teaching the comment above it: the exponential form
    // approaches 1 and never reaches or passes it, so overshoot is impossible
    // by construction and the clamp is belt-and-braces rather than the
    // guarantee. The linear form it replaced genuinely did overshoot.
    // 0.5s was in this list at first and failed at 0.897 — correctly, because
    // half a second is only 2.3 time constants and not a "long frame" at all.
    // The bound belongs on genuinely stalled frames.
    for (const dt of [5, 50, 1e6]) {
      expect(approachRate(dt, 0.22)).toBeLessThanOrEqual(1)
      expect(approachRate(dt, 0.22)).toBeGreaterThan(0.99)
    }

    // Never negative, never above 1, for anything a clock can produce.
    for (const dt of [1 / 240, 1 / 24, 0.5, 5]) {
      const k = approachRate(dt, 0.22)
      expect(k).toBeGreaterThan(0)
      expect(k).toBeLessThanOrEqual(1)
    }
  })

  it('does not move on a zero or negative frame', () => {
    expect(approachRate(0, 0.22)).toBe(0)
    expect(approachRate(-1, 0.22)).toBe(0)
  })
})
