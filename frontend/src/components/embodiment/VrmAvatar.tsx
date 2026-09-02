import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { VRMLoaderPlugin, VRMUtils, type VRM } from '@pixiv/three-vrm'
import { useEmbodimentState, type EmbodimentState } from '@/hooks/useEmbodimentState'
import { useSpeechStore } from '@/stores/speechStore'
import { VISEMES, visemeAt, type Viseme } from '@/lib/visemes'
import { inspectAvatar } from '@/lib/vrmSafety'

// Keep the fetched VRM in memory across mounts.
//
// This component unmounts when a surface opens and remounts on the way back to
// the landing, and three.js ships its file cache *disabled*, so every return
// re-fetched the whole model before it could draw anything. That is the empty
// avatar panel for several seconds after coming back from a menu — the
// conspicuous cost of a round trip nobody needed to pay twice.
//
// `THREE.Cache` is keyed by URL and read by the `FileLoader` underneath
// `GLTFLoader`, so enabling it is the entire change; a remount now goes
// straight to parsing. It holds one avatar's bytes, which is the right trade
// against re-reading tens of megabytes on every navigation.
//
// Parsing still happens per mount. Removing that too means keeping the
// renderer mounted and pausing its loop instead of tearing it down, which is a
// larger change to the component's lifecycle and is worth doing separately.
THREE.Cache.enabled = true

/**
 * The VRM renderer — the orb's job with more bandwidth.
 *
 * `docs/EMBODIMENT-SPIKE.md` fixes the constraint before any code: **the avatar
 * embodies what the system is doing.** Thinking versus idle, listening,
 * speaking, swapping. Not a personality, not a name, not a relationship.
 *
 * **It no longer embodies which model answered** — narrowed 13 August 2026.
 * Locality is stated in words by `OrbStatusLabel`, which renders beside this
 * component under either renderer and can express a distinction a rim colour
 * cannot. Reasoning in `useEmbodimentState`.
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

/** The rim light says whether the system is working, and nothing else.
 *
 *  It used to carry locality as well — cyan for what stayed on the device,
 *  violet for what left. Removed 13 August 2026: `LivingOrb` never rendered
 *  locality, so this was the only renderer that did and the two disagreed about
 *  what they report. `OrbStatusLabel` states it in words, with a distinction a
 *  colour cannot make ("Local · can send" is not "Cloud enabled"), and a face
 *  that reports routing is a face read as a someone. Reasoning in
 *  `useEmbodimentState`.
 *
 *  So: slate at rest, cyan while working, dim slate while nothing is resident.
 *  Three values, no legend to learn. */
const RIM_COLOUR: Record<EmbodimentState, number> = {
  idle: 0x93a3b8,
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
  thinking: 1.6,
  listening: 1.2,
  speaking: 1.4,
  swapping: 0.45,
}

/**
 * Render tuning now lives in `@/lib/renderTuning` — a second renderer needed
 * the same three functions and neither of them is VRM-specific. Re-exported
 * here because they are part of this module's tested surface and moving the
 * import site is a change to the tests, not to the behaviour.
 */
export { renderScaleFor, approachRate, applyTextureFiltering, RIM_EASE_SECONDS } from '@/lib/renderTuning'
import { renderScaleFor, approachRate, applyTextureFiltering, RIM_EASE_SECONDS } from '@/lib/renderTuning'


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

    // Nothing this loader resolves may leave the machine.
    //
    // A `.vrm` is a file somebody else wrote, and glTF `buffers` and `images`
    // carry an optional `uri` that the loader fetches. An absolute `https://`
    // one is a request no gate in this product can see: `EgressGate` intercepts
    // what the *backend* sends, and `check-no-remote-assets.mjs` scans *source*.
    // A URL inside a binary asset is invisible to both, so rule 3 — every byte
    // that leaves is logged — would be broken by a data file with nothing
    // anywhere reporting it. It is also a working beacon: whoever authored the
    // avatar learns the user's IP and when they opened Zaram.
    //
    // Two layers, deliberately. `inspectAvatar` refuses the file before a
    // single request is made and can say why; the modifier below is the
    // structural backstop for anything the scan did not recognise as a URI, and
    // it fails to a broken model rather than to a silent request. Belt and
    // braces on the one path where the failure is invisible.
    //
    // **The two loaders get different managers, and the first version of this
    // did not.** A `LoadingManager`'s URL modifier applies to *every* URL that
    // manager resolves — including the avatar's own, which is not a data URI
    // and was therefore replaced with an empty one. The bundled avatar then
    // arrived as zero bytes and the gate refused it as unreadable: the guard
    // blocked the very file it was written to protect. Shipped without looking
    // at it, which is exactly what the handoff had just finished warning about.
    //
    // So the restrictive manager governs *sub-resource resolution during parse*
    // and nothing else. The top-level fetch is an ordinary load of a path this
    // component chose, not a URI a stranger's file asked for, and the two must
    // not be governed by the same rule.
    const parseManager = new THREE.LoadingManager()
    parseManager.setURLModifier((url) => {
      if (url.startsWith('data:') || url.startsWith('blob:')) return url
      console.warn(`[embodiment] refused an external avatar resource: ${url}`)
      return 'data:application/octet-stream;base64,'
    })

    const loader = new GLTFLoader(parseManager)
    loader.register((parser) => new VRMLoaderPlugin(parser))

    const clock = new THREE.Clock()
    let blinkAt = 2 + Math.random() * 3
    // Allocated once. A `new THREE.Color()` per frame is 60 allocations a
    // second on a surface that renders permanently beside a resident model.
    const rimTarget = new THREE.Color()

    // Fetched as bytes and inspected before parsing, rather than handed
    // straight to `loader.load`. Reading the glTF JSON first is the only point
    // at which an external URI can be refused *before* the loader resolves it.
    // `FileLoader` rather than `fetch` so `THREE.Cache` still serves a remount.
    // The default manager, deliberately — see the note above `parseManager`.
    const bytes = new THREE.FileLoader()
    bytes.setResponseType('arraybuffer')
    bytes.load(
      src,
      (data) => {
        if (disposed) return
        const buffer = data as ArrayBuffer
        const verdict = inspectAvatar(buffer)
        if (!verdict.ok) {
          setStatus('failed')
          setReason(verdict.reason)
          console.warn(`[embodiment] refused ${src}: ${verdict.reason}`, verdict.external)
          return
        }
        loader.parse(buffer, '', onLoaded, onLoadError)
      },
      undefined,
      (err) => {
        if (disposed) return
        setStatus('failed')
        setReason(err instanceof Error ? err.message : 'The avatar file could not be read.')
      },
    )

    function onLoaded(gltf: { scene: THREE.Group; userData: { vrm?: VRM } }) {
      {
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
      }
    }

    function onLoadError(err: unknown) {
      if (disposed) return
      setStatus('failed')
      // Named, never silent. A blank square where a face should be is
      // indistinguishable from a code bug, which is the same reason the
      // ingest path reports why a file could not be read.
      setReason(err instanceof Error ? err.message : 'The avatar file could not be read.')
    }

    const tick = () => {
      raf = requestAnimationFrame(tick)
      const dt = clock.getDelta()
      const now = clock.elapsedTime
      const s = stateRef.current
      const rate = MOTION_RATE[s]

      // Eased, not assigned. Both are pushed toward the state's value rather
      // than set to it, so a state change is a short crossfade in the one
      // channel that carries state. `Color.lerp` interpolates in linear RGB,
      // which is what keeps slate-to-cyan from passing through a muddy middle.
      const k = approachRate(dt, RIM_EASE_SECONDS)
      rimTarget.setHex(RIM_COLOUR[s])
      rim.color.lerp(rimTarget, k)
      rim.intensity = THREE.MathUtils.lerp(rim.intensity, s === 'swapping' ? 1.1 : 2.2, k)

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
          // Same time constant the old `dt * 3` produced at 60Hz, now the same
          // at any refresh rate — see `approachRate`.
          const kHead = approachRate(dt, 1 / 3)
          head.rotation.z = THREE.MathUtils.lerp(head.rotation.z, tilt, kHead)
          head.rotation.x = THREE.MathUtils.lerp(
            head.rotation.x,
            lean + Math.sin(now * 0.7 * rate) * 0.008,
            kHead,
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
          const kMouth = approachRate(dt, 1 / 15)
          for (const v of VISEMES) {
            const target = shape === v ? (v === 'aa' ? 0.85 : 0.6) : 0
            em.setValue(v, THREE.MathUtils.lerp(em.getValue(v) ?? 0, target, kMouth))
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
