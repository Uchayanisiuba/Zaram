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
import { renderScaleFor, applyTextureFiltering } from './VrmAvatar'

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
