import * as THREE from 'three'

/**
 * Render-quality settings shared by every 3D renderer in the product.
 *
 * These moved out of `VrmAvatar` when a second renderer arrived. They are not
 * VRM-specific — one is about the display, one is about time, one walks a
 * material graph — and a second copy of them would be two places to get the
 * same subtle thing wrong. Importing them from `VrmAvatar` was the other
 * option and would have pulled `@pixiv/three-vrm` into a bundle that does not
 * need it, which is the cost `Embodiment.tsx` lazily loads to avoid.
 */

/**
 * How many device pixels to render per CSS pixel.
 *
 * **The avatar was pixelated because this used to be `min(dpr, 2)`**, and the
 * measurement is the whole argument: on a DPR-1 display that renders the entire
 * head into a **320x320** buffer, and the head only occupies part of it. The
 * cap was doing its job; there was no floor, and a face is not a page of text.
 *
 * `antialias: true` was already set and was not the fix — confirmed live at
 * `SAMPLES = 4`. MSAA smooths *silhouettes*. It does nothing for shading and
 * texture sampling inside a surface, which is where the aliasing on a face
 * actually lives, so the setting that looked like the answer was already on.
 *
 * Rendering at 2 on a DPR-1 display is supersampling: 640x640 resolved down to
 * 320 CSS px. The old comment here priced that as unaffordable next to a
 * resident local model, and the arithmetic says otherwise — 409,600 fragments
 * against the 2,073,600 of a single 1080p frame. It is a fifth of one frame of
 * the screen it is drawn on.
 *
 * Still capped at 2. Above that the returns are invisible at this size and the
 * cost is real, so a DPR-3 display renders slightly soft on purpose.
 */
export function renderScaleFor(devicePixelRatio: number): number {
  return Math.min(Math.max(devicePixelRatio, 2), 2)
}

/**
 * How far to move toward a target this frame, given how long the move takes.
 *
 * **State changes used to be cuts.** The rim light is the state channel, and it
 * was assigned absolutely every frame — `rim.color.setHex(RIM_COLOUR[s])` — so
 * going from idle to thinking swapped slate for cyan between two frames. On a
 * surface whose whole brief is *calm over delight*, an instant colour flip is
 * the one motion that reads as a glitch rather than as a state.
 *
 * **Frame-rate independent, which the lerps already here are not.**
 * `lerp(a, b, dt * 3)` moves three times further per second at 144Hz than at
 * 48Hz, so the same avatar eases at visibly different speeds on different
 * machines and the tuning is only correct on the one it was tuned on. The
 * exponential form is the standard fix: `1 - e^(-dt/τ)` covers the same
 * fraction of the remaining distance per unit of *time* rather than per frame.
 *
 * `seconds` is the time constant — roughly 63% of the way there. Three of them
 * is close enough to be indistinguishable from arrived.
 *
 * **The clamp is defensive, not load-bearing, and the test says which.** A long
 * frame — a tab returning to the foreground, a model finishing a load — is
 * exactly what made the linear form dangerous: `dt * 3` at `dt = 5` is 15, so
 * the value flies past its target and springs back. `1 - e^(-dt/τ)` cannot
 * exceed 1 for any finite input, so overshoot is impossible by construction
 * here. `Math.min` stays because it costs nothing and the next person to change
 * this formula may reintroduce the hazard, but the guarantee comes from the
 * shape of the function rather than from the clamp.
 */
export function approachRate(dt: number, seconds: number): number {
  if (!(dt > 0)) return 0;
  if (!(seconds > 0)) return 1;
  return Math.min(1, 1 - Math.exp(-dt / seconds));
}

/** How long the rim light takes to reach a new state's colour.
 *
 *  Slow enough to read as a transition rather than a cut, short enough that the
 *  indicator is not still catching up when the thing it indicates has moved on.
 *  Thinking can be over in under a second, so this cannot be much longer. */
export const RIM_EASE_SECONDS = 0.22

/**
 * Turn on anisotropic filtering for every texture under `root`.
 *
 * The second half of the pixelation, and the larger half. three.js defaults
 * `Texture.anisotropy` to **1**, which is no anisotropic filtering at all. This
 * asset carries six 2048x2048 maps rendered onto a head a couple of hundred
 * pixels tall — around 10x minification — and at anisotropy 1 that samples one
 * texel per fragment and shimmers.
 *
 * Texture slots are found by walking the material rather than by naming `map`,
 * `normalMap` and friends, because VRM materials are MToon and carry
 * `shadeMultiplyTexture`, `rimMultiplyTexture`, `matcapTexture` and others that
 * a hardcoded list would silently skip — and skipping the shade map on a
 * cel-shaded face misses the aliasing everyone can see.
 *
 * **Two places have to be searched, and the second one is the one that
 * matters.** The first version of this walked `Object.values(material)` only.
 * It passed its unit test against a `MeshBasicMaterial` and reported
 * `textures filtered: 0` against the real avatar, because `MToonMaterial`
 * extends `ShaderMaterial` and exposes its maps as *prototype accessors* over
 * `this.uniforms` — and `Object.values` on the instance enumerates neither
 * prototype properties nor accessors. The count is printed at load for exactly
 * this reason: the fix looked right, the test agreed, and the number said no.
 *
 * Returns how many textures were changed, so a caller can tell "filtering
 * applied" from "there was nothing to apply it to".
 */
export function applyTextureFiltering(root: THREE.Object3D, maxAnisotropy: number): number {
  const seen = new Set<THREE.Texture>()

  const filter = (value: unknown) => {
    if (!(value instanceof THREE.Texture) || seen.has(value)) return
    seen.add(value)
    value.anisotropy = maxAnisotropy
    // Mipmaps are what anisotropic filtering samples between. A texture set to
    // NearestFilter has none, and would keep aliasing however high the
    // anisotropy went — so the two are set together or not at all.
    value.minFilter = THREE.LinearMipmapLinearFilter
    value.magFilter = THREE.LinearFilter
    value.generateMipmaps = true
    value.needsUpdate = true
  }

  root.traverse((object) => {
    const material = (object as THREE.Mesh).material
    if (!material) return
    for (const entry of Array.isArray(material) ? material : [material]) {
      // Ordinary materials: the texture is an own property.
      for (const value of Object.values(entry)) filter(value)
      // ShaderMaterial and everything built on it, MToon included: the texture
      // is a uniform, and the named property is an accessor pointing at it.
      const uniforms = (entry as unknown as { uniforms?: Record<string, { value?: unknown }> }).uniforms
      if (uniforms) {
        for (const uniform of Object.values(uniforms)) filter(uniform?.value)
      }
    }
  })

  return seen.size
}
