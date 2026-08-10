import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { VRMLoaderPlugin, VRMUtils, type VRM } from '@pixiv/three-vrm'
import { useEmbodimentState, type EmbodimentState } from '@/hooks/useEmbodimentState'
import { useSpeechStore } from '@/stores/speechStore'
import { VISEMES, visemeAt, type Viseme } from '@/lib/visemes'

/**
 * The VRM renderer — the orb's job with more bandwidth.
 *
 * `docs/EMBODIMENT-SPIKE.md` fixes the constraint before any code: **the avatar
 * embodies which model is answering and what it is doing.** Local versus cloud,
 * thinking versus idle, speaking. Not a personality, not a name, not a
 * relationship.
 *
 * That line decides every argument below. The moment the avatar has a name,
 * users form a relationship with a status indicator, and every routing decision
 * it displays becomes a thing *she* did rather than a thing the system did.
 * Zaram's whole claim is that the machine is legible; a character that invites
 * projection is the opposite of legible.
 *
 * Concretely ruled out, and these are omissions rather than oversights: gaze
 * that wanders, fidgeting, reacting to being watched, any name or pronoun, and
 * expressions not derived from system state. Ruled in: the same states the orb
 * has, rendered with a face.
 *
 * Blinking and breathing stay, and the distinction is worth stating because it
 * is the one judgement call here. They are not personality — they are the
 * difference between a resting face and a corpse, and their absence reads as a
 * crash rather than as calm. They carry no information and never vary by state.
 */

/** Colour is the same vocabulary the orb and the citation chips already use:
 *  cyan for what stayed on the device, violet for what left, slate for a swap.
 *  One meaning reused, so the avatar needs no legend of its own. */
const RIM_COLOUR: Record<EmbodimentState, number> = {
  idle: 0x93a3b8,
  local: 0x78dcf0,
  cloud: 0xc084fc,
  thinking: 0x78dcf0,
  listening: 0x78dcf0,
  speaking: 0x78dcf0,
  // Every other state animates faster to signal effort. A swap is the one state
  // where nothing is resident and no work is being done, so it is dimmer and
  // slower, in desaturated slate.
  swapping: 0x64748b,
}

/** How lively the resting motion is. Swapping is deliberately the slowest. */
const MOTION_RATE: Record<EmbodimentState, number> = {
  idle: 1,
  local: 1,
  cloud: 1,
  thinking: 1.6,
  listening: 1.2,
  speaking: 1.4,
  swapping: 0.45,
}

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

interface VrmAvatarProps {
  /** Rendered box, in px. Matches the orb's `px` so the two are swappable. */
  px?: number
  /** Where the model lives. Public path, not an import — a 16 MB binary must
   *  not enter the bundle graph.
   *
   *  Served from `/avatars/`, deliberately **not** `/models/`. The latter is the
   *  backend's namespace: `vite.config.ts` proxies `/models` to port 8420 for
   *  the provider model listing, so a VRM sitting in `public/models/` is never
   *  served by Vite at all — it is forwarded to the backend and comes back 500.
   *  Found by driving it; the file loaded fine and the request never arrived. */
  src?: string
}

export default function VrmAvatar({ px = 320, src = '/avatars/AvatarSample_Z.vrm' }: VrmAvatarProps) {
  const mountRef = useRef<HTMLDivElement | null>(null)
  const stateRef = useRef<EmbodimentState>('idle')
  const [status, setStatus] = useState<'loading' | 'ready' | 'failed'>('loading')
  const [reason, setReason] = useState<string | null>(null)

  const state = useEmbodimentState()
  // The render loop reads this ref rather than closing over the prop, so a
  // state change never rebuilds the scene or reloads 16 MB of model.
  stateRef.current = state

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    let disposed = false
    let raf = 0
    let vrm: VRM | null = null

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 20)
    // alpha:true so the avatar sits on the landing's own backdrop rather than
    // painting a second ground over it.
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setSize(px, px)
    renderer.setPixelRatio(renderScaleFor(window.devicePixelRatio))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    mount.appendChild(renderer.domElement)

    const key = new THREE.DirectionalLight(0xffffff, 1.5)
    key.position.set(1, 1, 1.5)
    scene.add(key)
    scene.add(new THREE.AmbientLight(0xffffff, 0.55))
    // The rim light is the state channel. It is a light rather than a material
    // change so it reads on any avatar the user loads, not just this one.
    const rim = new THREE.DirectionalLight(RIM_COLOUR.idle, 2.2)
    rim.position.set(-1.4, 0.6, -1)
    scene.add(rim)

    const loader = new GLTFLoader()
    loader.register((parser) => new VRMLoaderPlugin(parser))

    const clock = new THREE.Clock()
    let blinkAt = 2 + Math.random() * 3

    loader.load(
      src,
      (gltf) => {
        if (disposed) return
        const loaded = gltf.userData.vrm as VRM | undefined
        if (!loaded) {
          setStatus('failed')
          setReason('The file loaded but carries no VRM data.')
          return
        }
        vrm = loaded

        // Cheap wins, both from the three-vrm docs: unused vertices and split
        // skeletons cost frames on a surface that renders permanently.
        VRMUtils.removeUnnecessaryVertices(gltf.scene)
        VRMUtils.combineSkeletons(gltf.scene)
        // VRM0 models face +Z; VRM1 face -Z. This normalises the older ones so
        // the camera code below does not need to know which it got.
        VRMUtils.rotateVRM0(vrm)

        vrm.scene.traverse((o) => {
          // Nothing here casts or receives shadows, and frustum culling on a
          // skinned mesh that is always on screen only costs a test.
          o.frustumCulled = false
        })
        // After VRMUtils and before the first frame: the loader leaves every
        // texture at three.js's default anisotropy of 1.
        const filtered = applyTextureFiltering(vrm.scene, renderer.capabilities.getMaxAnisotropy())
        scene.add(vrm.scene)

        // The named requirement from the spike: log every expression the model
        // actually has. A missing viseme is otherwise silently
        // indistinguishable from a bug in this file.
        const expressions = vrm.expressionManager?.expressions ?? []
        const names = expressions.map((e) => e.expressionName)
        // eslint-disable-next-line no-console
        console.info(
          `[embodiment] ${src}\n` +
            `  expressions (${names.length}): ${names.join(', ') || 'none'}\n` +
            `  visemes present: ${['aa', 'ih', 'ou', 'ee', 'oh'].filter((v) => names.includes(v)).join(', ') || 'none'}\n` +
            `  humanoid: ${vrm.humanoid ? 'yes' : 'no'}\n` +
            // Printed because both were silently wrong and looked right: the
            // buffer was 320x320 on a DPR-1 display, and every texture sat at
            // anisotropy 1. Neither is visible in the code that sets them.
            `  render buffer: ${px * renderer.getPixelRatio()}px for a ${px}px box\n` +
            `  textures filtered: ${filtered} at anisotropy ${renderer.capabilities.getMaxAnisotropy()}`,
        )
        if (names.length === 0) {
          setReason('This avatar has no expressions, so only head motion will respond to state.')
        }

        // A VRM loads in T-pose, because a T-pose is the rig's rest position
        // and nothing has posed it. Left uncorrected the avatar stands with its
        // arms straight out — which reads as a broken model rather than as a
        // calm one, and no amount of expression work rescues it.
        //
        // This is a *pose*, not an animation: the arms are placed once and then
        // left alone. An idle animation cycle is exactly what the spike rules
        // out, because motion with no system meaning reads as personality.
        const rest: [string, number][] = [
          ['leftUpperArm', -1.18],
          ['rightUpperArm', 1.18],
          ['leftLowerArm', -0.18],
          ['rightLowerArm', 0.18],
        ]
        for (const [bone, z] of rest) {
          const node = vrm.humanoid?.getNormalizedBoneNode(bone as never)
          if (node) node.rotation.z = z
        }

        // Frame the head from the humanoid rig rather than from a guessed
        // height. Avatars differ in scale and a hardcoded camera puts a short
        // one out of frame — the kind of thing that reads as a broken renderer.
        const head = vrm.humanoid?.getNormalizedBoneNode('head')
        const target = new THREE.Vector3(0, 1.35, 0)
        if (head) head.getWorldPosition(target)
        // Head and shoulders. The orb occupies a 320px circle and the avatar
        // replaces it in the same space, so a full body would render the face —
        // the only part carrying state — a few dozen pixels tall.
        camera.position.set(0, target.y - 0.07, 1.08)
        camera.lookAt(0, target.y - 0.07, 0)

        setStatus('ready')
      },
      undefined,
      (err) => {
        if (disposed) return
        setStatus('failed')
        // Named, never silent. A blank square where a face should be is
        // indistinguishable from a code bug, which is the same reason the
        // ingest path reports why a file could not be read.
        setReason(err instanceof Error ? err.message : 'The avatar file could not be read.')
      },
    )

    const tick = () => {
      raf = requestAnimationFrame(tick)
      const dt = clock.getDelta()
      const now = clock.elapsedTime
      const s = stateRef.current
      const rate = MOTION_RATE[s]

      rim.color.setHex(RIM_COLOUR[s])
      rim.intensity = s === 'swapping' ? 1.1 : 2.2

      if (vrm) {
        const em = vrm.expressionManager
        const head = vrm.humanoid?.getNormalizedBoneNode('head')
        const chest = vrm.humanoid?.getNormalizedBoneNode('chest')

        // Breathing. Constant across states — it is liveness, not information.
        if (chest) chest.rotation.x = Math.sin(now * 0.9 * rate) * 0.012

        if (head) {
          // Thinking leans the head a few degrees and holds it there; listening
          // brings it fractionally forward. Both are small on purpose: this is
          // a status indicator, and a head that swings reads as a character.
          const tilt = s === 'thinking' ? 0.09 : 0
          const lean = s === 'listening' ? 0.06 : 0
          head.rotation.z = THREE.MathUtils.lerp(head.rotation.z, tilt, dt * 3)
          head.rotation.x = THREE.MathUtils.lerp(
            head.rotation.x,
            lean + Math.sin(now * 0.7 * rate) * 0.008,
            dt * 3,
          )
        }

        if (em) {
          // Blink. Not state-dependent, for the same reason as breathing.
          blinkAt -= dt
          const blinking = blinkAt < 0.12
          em.setValue('blink', blinking ? 1 : 0)
          if (blinkAt < 0) blinkAt = 2.5 + Math.random() * 3.5

          // Lip sync, driven by Kokoro's own phoneme timings scrubbed against
          // playback position — not a cycle. `audio.currentTime` is the clock
          // rather than an elapsed counter, because the two diverge the moment
          // audio buffers or the tab is backgrounded, and a mouth drifting out
          // of sync is worse than one that does not move.
          //
          // Read from the store per frame rather than through a React
          // subscription: a 60 Hz state update would re-render the tree to move
          // a jaw.
          const { audio, track } = useSpeechStore.getState()
          const talking = s === 'speaking'
          let shape: Viseme = 'sil'
          if (talking && audio && track.length > 0) {
            shape = visemeAt(track, audio.currentTime)
          } else if (talking) {
            // No timings — an engine that cannot produce them, or audio Zaram
            // did not generate. Fall back to plausible motion rather than a
            // still mouth. This is the seam the spike reserved for
            // amplitude-based sync, and it is deliberately the lesser path.
            shape = Math.sin(now * 9) > 0 ? 'aa' : 'ih'
          }
          // Ease rather than snap. Blend shapes switched instantly read as a
          // puppet; a short lerp at ~15 Hz still resolves every cue at speech
          // rate while looking like a jaw with mass.
          for (const v of VISEMES) {
            const target = shape === v ? (v === 'aa' ? 0.85 : 0.6) : 0
            em.setValue(v, THREE.MathUtils.lerp(em.getValue(v) ?? 0, target, dt * 15))
          }

          // A swap is the one state where nothing is resident and no work is
          // happening. The face goes quiet rather than sad — "sad" would be an
          // emotion not derived from system state.
          em.setValue('relaxed', s === 'swapping' ? 0.5 : 0)
        }

        vrm.update(dt)
      }

      renderer.render(scene, camera)
    }
    tick()

    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      if (vrm) VRMUtils.deepDispose(vrm.scene)
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
    }
    // px and src rebuild the scene; embodiment state deliberately does not.
  }, [px, src])

  return (
    <div style={{ width: px, height: px, position: 'relative' }}>
      {/* The orb occupies a circle; a WebGL canvas is a hard-edged square, and
          the seam where it meets the backdrop is the first thing the eye finds.
          A radial fade puts the avatar in the same space the orb held rather
          than in a window cut into the surface. Pure CSS — no second render
          target, no post-processing pass competing with local inference. */}
      <div
        ref={mountRef}
        style={{
          width: px,
          height: px,
          WebkitMaskImage: 'radial-gradient(circle at 50% 45%, #000 58%, transparent 76%)',
          maskImage: 'radial-gradient(circle at 50% 45%, #000 58%, transparent 76%)',
        }}
      />
      {status !== 'ready' && (
        <div
          className="absolute inset-0 flex items-center justify-center text-center px-6"
          style={{ fontSize: 12, color: status === 'failed' ? '#fca5a5' : '#64748b' }}
        >
          {status === 'loading' ? 'Loading avatar…' : `Avatar unavailable — ${reason}`}
        </div>
      )}
    </div>
  )
}
