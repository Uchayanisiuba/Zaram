import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { useEmbodimentState, type EmbodimentState } from '@/hooks/useEmbodimentState'
import { useSpeechStore } from '@/stores/speechStore'
import { visemeAt } from '@/lib/visemes'
import { inspectAvatar } from '@/lib/vrmSafety'
import { renderScaleFor, approachRate, applyTextureFiltering, RIM_EASE_SECONDS } from '@/lib/renderTuning'
import {
  EYE_CELLS, MOUTH_CELLS, transformForCell, texelAspect, uvIslandOf,
  type EyeCell, type MouthCell, type UvIsland,
} from '@/lib/faceAtlas'
import { ShuffleBag, clipsByState, clipNameOf, type AnimationManifest } from '@/lib/animationSet'

THREE.Cache.enabled = true

/**
 * The Zaram robot — a glTF character with an LED sprite face.
 *
 * It sits beside `VrmAvatar` rather than inside it. The two renderers answer
 * the same question and share `renderTuning`, but almost nothing else: a VRM
 * has a humanoid rig, an expression manager and a normalized bone hierarchy,
 * and this character has none of those. Folding both into one component would
 * produce a file where every second branch asks which kind of avatar it got.
 *
 * **Being a plain glTF is a simplification, not a compromise**, and it removes
 * three failure modes a VRM build of the same character would have had. There
 * is no normalized rig, so animation tracks bind to the bones they name rather
 * than being silently overwritten by `vrm.update()` every frame. There is no
 * expression manager interpolating weights, so a sprite cell cannot be
 * half-applied and land on the seam between two mouths. And there are no
 * additive expression binds to sum into a cell that does not exist. The VRM
 * path stays exactly where it is, for avatars users bring themselves.
 *
 * What none of that changes: this embodies **what the system is doing**. Clips
 * vary so the loop is not obvious, never so the character seems to have moods —
 * every variant of a state settles into the same read.
 */

/**
 * A number from the query string, or the fallback.
 *
 * **This exists because `Number(null)` is `0`, and that cost this session
 * several hours of chasing lighting that was not the lighting.**
 * `URLSearchParams.get` returns `null` for an absent key, `Number(null)` is `0`
 * rather than `NaN`, and `0` is finite and `>= 0` — so every guard written as
 * `Number.isFinite(raw) && raw >= 0 ? raw : fallback` silently returned **zero**
 * whenever the parameter was missing, which is to say always, outside a debug
 * URL.
 *
 * The failures it produced all looked like something else. The environment
 * intensity read 0, so the character rendered black and the fix was assumed to
 * be in the environment — four of them were rebuilt. The glow opacity read 0, so
 * the glow was invisible and was assumed not to be rendering. The normal scale
 * read 0, flattening the surface. Every one of those was diagnosed as a
 * different bug, and passing the value explicitly in the URL "fixed" it each
 * time, which is exactly what made the parameter look innocent.
 *
 * Guards written `raw > 0` escaped by accident, because `0 > 0` is false. That
 * is not a defence, it is a coin toss, so every reader goes through here now.
 */
function numberParam(name: string, fallback: number, min = -Infinity): number {
  const raw = new URLSearchParams(window.location.search).get(name)
  if (raw === null) return fallback
  const value = Number(raw)
  return Number.isFinite(value) && value >= min ? value : fallback
}

/** The rim light is the state channel. Deliberately the same three values as
 *  `VrmAvatar` — two renderers reporting one state in different colours is the
 *  defect the 13 August narrowing was written to stop. */
const RIM_COLOUR: Record<EmbodimentState, number> = {
  idle: 0x93a3b8,
  thinking: 0x78dcf0,
  listening: 0x78dcf0,
  speaking: 0x78dcf0,
  swapping: 0x64748b,
}

/** Which eye cell a state wears. Blink overrides it briefly; nothing else does,
 *  because an expression not derived from a state is a personality. */
const EYES_FOR_STATE: Record<EmbodimentState, EyeCell> = {
  idle: 'open',
  thinking: 'thinking',
  listening: 'listening',
  speaking: 'open',
  swapping: 'swapping',
}

/**
 * How often the idle mouth breaks from `sil` into a smile, and for how long.
 *
 * **This is the one expression here not derived from a system state, and that is
 * a deliberate exception the maintainer asked for.** `CLAUDE.md` says the rest
 * face is `sil`, a flat line, not a smile, on the grounds that a face showing
 * expressions of its own reads as a *someone* rather than as a status indicator.
 * The precedent that makes it survivable is blink: already here, already not
 * state-derived, and read as liveliness rather than as mood because it carries
 * no meaning and resolves immediately.
 *
 * So the same discipline applies. Rare enough that it is never the thing you are
 * looking at, and **idle only** — during thinking, listening, speaking or
 * swapping the face belongs to the state and to lip sync, and an expression
 * arriving over those would be the character editorialising about the work.
 *
 * **The eyes smile with the mouth**, because a mouth that curves while the eyes
 * hold still is the shape of an insincere smile and reads as one. A real smile
 * raises the lower lid and squeezes the eye into a crescent; every social robot
 * that expresses through a screen rather than a face abbreviates that the same
 * way, as an upward arc. `happy` is that arc, and it suppresses the blink for as
 * long as it shows — a blink over an already-curved eye reads as a glitch rather
 * than as a blink.
 */
const SMILE_SECONDS = 12.8
const SMILE_GAP_MIN = 14
const SMILE_GAP_MAX = 32

/** How long to wait between smiles, overridable as `?smileEvery=2`.
 *
 *  Here because the shipped gap is 14-32 seconds and nobody should have to sit
 *  through that to check a sprite. The same reason `?noAnim=1` exists: the
 *  alternative is editing a constant, rebuilding, and remembering to put it
 *  back — which is how a debug value ships. */
function smileGap(): [number, number] {
  const every = numberParam('smileEvery', 0, 0.1)
  return every > 0 ? [every, every] : [SMILE_GAP_MIN, SMILE_GAP_MAX]
}

/** How long a state change takes to cross into its new clip. Long enough to
 *  read as a transition rather than a cut, short enough that a state lasting
 *  under a second is not still arriving when it ends. */
const CLIP_FADE_SECONDS = 0.35

/** How long one variant of a state takes to blend into another. Longer than a
 *  state change, because nothing has happened to justify a visible transition —
 *  the point is that the viewer never notices the clip changed at all. */
const VARIANT_FADE_SECONDS = 0.9

/** The head-to-hips span of the avatar these camera numbers were tuned on, in
 *  metres. Everything below scales against it, so a taller or shorter
 *  character fills the same portion of the box instead of overflowing it. */
const REFERENCE_SPAN = 0.564

/**
 * Finger joints, which are posed once rather than animated.
 *
 * They *are* in the mocap — the load log shows only 13 bones without tracks
 * and every one of them is a leaf tip. The problem is the retarget: the
 * rest-offset correction that works across the torso and arms breaks down on
 * finger chains, where the two rigs' local axes differ most, and the result is
 * a hand held rigidly splayed. Fingers carry no system state, so the honest
 * answer is to stop animating them and hold a relaxed curl — a pose, not an
 * animation, the same call `VrmAvatar` makes about its arms.
 */
const FINGER_BONE = /Hand(Thumb|Index|Middle|Ring|Pinky)\d/i

/**
 * How far two rigs' rest poses may differ before they count as disagreeing,
 * in radians (about 3 degrees).
 *
 * Below this, clips authored against one rig play correctly on the other and
 * nothing needs correcting. Above it, every rotation is expressed in a frame
 * the character does not share, and no closed-form correction recovers it
 * reliably — the arms and fingers are where that shows.
 */
const RIG_MATCH_TOLERANCE = 0.05

/** How far each finger joint curls, in radians, when they have to be posed
 *  rather than animated. Distal joints curl further, which is the difference
 *  between a relaxed hand and a flat one. */
function fingerCurl(): number {
  return numberParam('fingerCurl', 0.32, 0.01)
}

/**
 * How much rougher every surface is made than the GLB asks for.
 *
 * **The helmet was chrome and the reference is matte, and that is a gloss
 * problem rather than a brightness one.** Turning the environment down far
 * enough to stop the shell blowing out took the whole character to a
 * silhouette, because on a near-mirror almost all the brightness you see *is*
 * the reflection — dimming it removes the surface along with the glare.
 *
 * Roughness is the control that separates them. A **multiplier** rather than a
 * floor, because it preserves the material's own relative gloss: the visor's
 * near-zero roughness stays the glossiest thing on the character while the
 * helmet's mid roughness moves far enough to stop mirroring. A floor would have
 * flattened both and taken the faceplate with it.
 *
 * three.js multiplies `material.roughness` by the map's green channel and then
 * clamps to 1, so values above 1 are meaningful here and cannot overshoot.
 *
 * Overridable as `?rough=`; `1` is the material exactly as exported.
 */
function roughnessBoost(): number {
  return numberParam('rough', 2.1, 0.01)
}

/**
 * How hard the normal map is applied, against the 1.0 the GLB asks for.
 *
 * **Left at 1, after 0.8 was tried and measured as a large regression.** The
 * intuition was that the map's fine grain is authored for a close render and
 * only reads as noise at the size the avatar occupies on the landing. What
 * actually happens is that easing it back takes most of the shell's light with
 * it: on a near-mirror surface the normal detail is what tilts micro-facets
 * toward the bright half of the sky, and flattening it points them all at the
 * dark ground instead. At 0.8 the helmet went from readable to nearly black,
 * with everything else held constant.
 *
 * So this is a knob rather than a correction, and the default is the map as
 * exported. Worth remembering that on a glossy asset the normal map is a
 * *lighting* control, not only a detail one.
 *
 * Overridable as `?normal=`; `1` is the map exactly as exported, `0` disables it.
 */
function normalStrength(): number {
  return numberParam('normal', 1, 0)
}

/** Atlas dimensions, needed to turn UV spans into texel counts. */
const ATLAS_W = 768
const ATLAS_H = 768

/**
 * How much of the vertical view the head should fill.
 *
 * Overridable from the URL (`?headFraction=0.2`) because framing is the one
 * thing here that cannot be reasoned to a number — it has to be looked at, and
 * a reload-and-eyeball loop beats editing a constant and rebuilding. A low
 * value pulls the camera back far enough to see the whole character, which is
 * the fastest way to answer "which way is it facing and where is it standing".
 */
function frameFraction(): number {
  const value = numberParam('headFraction', 0.5, 0.02)
  return value <= 1 ? value : 0.5
}

/** How hard the environment lights the armour. Overridable as `?envIntensity=`,
 *  because this and the framing are the two numbers that can only be settled by
 *  looking — too low and a glossy black character is a silhouette, too high and
 *  the helmet goes silver. */
function envIntensity(): number {
  return numberParam('envIntensity', 1.4, 0)
}

/**
 * A single multiplier on the key, fill and ambient, so "too dark" has one knob.
 *
 * **The rim is deliberately not scaled.** It is the state channel, and its
 * brightness is part of how a state reads; scaling it with the room would make
 * the working state look different on a bright build than on a dark one, which
 * is the one thing the indicator must not do.
 *
 * Overridable as `?lightScale=`.
 */
/**
 * A multiplier on the rim light, for looking at what it contributes.
 *
 * **Separate from `lightScale` on purpose, and defaulting to 1.** The rim is the
 * state channel — slate at rest, cyan while working — and its brightness is part
 * of how a state reads, so it must not move when the room does. This knob exists
 * to answer "is the rim doing anything", which on a character lit mostly by its
 * environment is a fair question, and not to tune it away.
 */
function rimScale(): number {
  return numberParam('rim', 1, 0)
}

function lightScale(): number {
  return numberParam('lightScale', 0.25, 0.01)
}

/**
 * The elevation profile of Blender's `forest` studio light, measured.
 *
 * Sixteen bands from nadir to zenith, mean linear RGB, straight off the file —
 * `avatar-source/probe_studio_reference.py` prints exactly this table. Copying
 * the numbers rather than the pixels is the whole approach: the environment
 * stays generated in code, and it stops being a guess.
 *
 * **Two features in here do all the work, and neither survived being invented.**
 * The sky is *cool* — blue above green above red — while the ground is *warm*,
 * red above green above blue, and about fourteen times darker. Every hand-built
 * environment before this used one colour for the whole sphere, and a
 * single-hue gradient reads as artificial the moment it lands on a curved
 * surface. And the transition is abrupt: band 8 to band 9, across the horizon,
 * jumps from 0.42 to 2.53. That step is what puts a defined bright edge along
 * the top of the helmet instead of a soft wash.
 *
 * Band 9's mean of 2.53 carries a peak of 81.75 — the sun through the trees.
 * Where that lands is a decision rather than a measurement, and it is made
 * below.
 */
const FOREST_PROFILE: readonly (readonly [number, number, number])[] = [
  [0.088, 0.078, 0.068], [0.094, 0.084, 0.074], [0.108, 0.094, 0.079], [0.126, 0.105, 0.083],
  [0.161, 0.128, 0.093], [0.196, 0.153, 0.104], [0.172, 0.142, 0.090], [0.137, 0.124, 0.069],
  [0.445, 0.425, 0.263], [2.751, 2.507, 2.119], [1.341, 1.438, 1.603], [1.171, 1.326, 1.610],
  [1.179, 1.388, 1.797], [1.298, 1.552, 2.136], [1.103, 1.371, 1.950], [1.298, 1.573, 2.217],
]

/**
 * How much the sky half of the environment is dimmed, leaving the ground alone.
 *
 * **This is the knob that dims the body without touching the visor, and it
 * exists because neither of the obvious two can.** `lightScale` cannot: measured
 * at 0.3 against 0.6 the character is near-indistinguishable, because the three
 * lights contribute very little here and the environment does nearly all of it.
 * `envIntensity` can, and it takes the visor down with it — halving it visibly
 * weakens the faceplate's gradient, which is the part that was working.
 *
 * The separation is possible because the two surfaces sample *different parts*
 * of the same environment. The shell is rough, so it integrates a wide cone and
 * is dominated by the bright sky. The visor is a mirror aimed at the viewer, so
 * it samples one direction — and with the sun deliberately placed behind the
 * character, that direction is the dark ground. Dimming the sky bands therefore
 * lands almost entirely on the body.
 *
 * Applied above the horizon only, which the measured profile puts at band 8: the
 * step from 0.42 to 2.53 between bands 8 and 9 *is* the horizon.
 *
 * Overridable as `?sky=`; `1` is the environment as measured.
 */
function skyScale(): number {
  return numberParam('sky', 0.5, 0)
}

/**
 * The environment the character reflects: `forest` rebuilt from its own numbers.
 *
 * **Three hand-built environments failed here before this one, each differently,
 * and the difference now is that this one is measured.** `RoomEnvironment` is
 * furnished, so a near-mirror visor showed recognisable armchairs sliding across
 * the character's face. A plain vertical gradient read flat and needed six times
 * the intensity to look lit. Soft panels in a dark shell painted a bright
 * rectangle over the faceplate, and moving them behind the character to get it
 * off the face took the visor back to black. All three were guesses at what a
 * captured environment looks like.
 *
 * `forest.exr` is the studio light the reference render was lit with, and it is
 * CC0 — Greg Zaal / Poly Haven, per the `license.txt` beside it in Blender's
 * `datafiles/studiolights/world`. So the profile above is lifted from it
 * directly, and this function is the same environment expressed as arithmetic:
 * no image in the bundle, no file, and nothing to fetch.
 *
 * **The sun is deliberately placed behind the character**, and that is the one
 * departure from the source. A mirror facing the viewer reflects the hemisphere
 * *behind the viewer*, so a bright feature in front is painted straight across
 * the faceplate — which is the reflection the maintainer has rejected twice. Put
 * it behind and the same light still rims the helmet and lifts the shoulders,
 * while what the visor reflects is the dark ground and the even part of the sky.
 * That is how a glossy black prop is lit in a real studio, and it is why the
 * reference render has a dark faceplate despite a bright environment.
 *
 * 64x32, which is the resolution the reflection wants: coarse enough that it
 * reads as a soft mottled gradient rather than a sharp picture of anywhere.
 */
function studioEnvironment(): THREE.DataTexture {
  const width = 64
  const height = 32
  const sky = skyScale()
  const data = new Float32Array(width * height * 4)

  for (let y = 0; y < height; y++) {
    // three.js samples an equirect as `v = asin(dir.y)/PI + 0.5`, so v = 1 is
    // the zenith, and a `DataTexture` has `flipY = false` — row 0 is v = 0, the
    // nadir. Blender's rows are bottom-up, so the measured table is already in
    // this order. Getting it backwards lights the character from underneath,
    // which happened once and looked like a material fault rather than a
    // coordinate one.
    const v = (y + 0.5) / height
    const band = v * (FOREST_PROFILE.length - 1)
    const low = FOREST_PROFILE[Math.floor(band)]
    const high = FOREST_PROFILE[Math.min(FOREST_PROFILE.length - 1, Math.floor(band) + 1)]
    const mix = band - Math.floor(band)

    for (let x = 0; x < width; x++) {
      // Azimuth, in the sampler's own terms: `u = atan2(z, x)/2PI + 0.5`, so
      // u = 0.75 is +Z, straight at the camera, and u = 0.25 is directly behind
      // the character. The lobe is centred there.
      const u = (x + 0.5) / width
      // A wide cosine rather than a disc. The source's sun is a point with a
      // peak of 81.75, and reproducing that faithfully would put a hard white
      // dot on the visor every time the head turned past it. Spread over a third
      // of the sphere it delivers the same light with no shape to reflect.
      const toward = Math.cos((u - 0.25) * Math.PI * 2) * 0.5 + 0.5
      const lobe = 0.7 + 1.9 * Math.pow(toward, 2.5)

      const i = (y * width + x) * 4
      const gain = lobe * (band >= 8 ? sky : 1)
      data[i] = (low[0] + (high[0] - low[0]) * mix) * gain
      data[i + 1] = (low[1] + (high[1] - low[1]) * mix) * gain
      data[i + 2] = (low[2] + (high[2] - low[2]) * mix) * gain
      data[i + 3] = 1
    }
  }

  const texture = new THREE.DataTexture(data, width, height, THREE.RGBAFormat, THREE.FloatType)
  texture.mapping = THREE.EquirectangularReflectionMapping
  texture.needsUpdate = true
  return texture
}

/**
 * The soft disc of light behind the character.
 *
 * Radial, smooth, and with no edge anywhere in it — a falloff that reaches zero
 * before the quad does, so what the viewer sees is a glow rather than a sprite
 * with a rim. Generated rather than shipped for the same reason the environment
 * is: it is four lines of maths and it would otherwise be a PNG in the bundle.
 */
function glowTexture(): THREE.DataTexture {
  const S = 128
  const data = new Uint8Array(S * S * 4)
  for (let y = 0; y < S; y++) {
    for (let x = 0; x < S; x++) {
      const dx = ((x + 0.5) / S) * 2 - 1
      const dy = ((y + 0.5) / S) * 2 - 1
      const r = Math.min(1, Math.hypot(dx, dy))
      // **A gentle falloff, because the size is capped and opacity saturates.**
      // The disc has to fit inside the frustum or it clips against the canvas,
      // and `material.opacity` stops doing anything above 1 — measured, 1.6 and
      // 2.6 render identically. So the only remaining way to make the glow read
      // is to fill more of the radius it is allowed: a 2.4 exponent concentrates
      // almost everything in the middle and leaves the outer half nearly empty.
      // 1.4 spreads it while still arriving at exactly zero on the edge, which is
      // what keeps the boundary invisible.
      const a = Math.pow(1 - r, 1.4)
      const i = (y * S + x) * 4
      data[i] = 255
      data[i + 1] = 255
      data[i + 2] = 255
      data[i + 3] = Math.round(a * 255)
    }
  }
  const tex = new THREE.DataTexture(data, S, S, THREE.RGBAFormat, THREE.UnsignedByteType)
  tex.needsUpdate = true
  return tex
}

/**
 * How bright the state glow is allowed to get, and how large.
 *
 * **Deliberately below the orb on both counts.** The orb is the system-state
 * indicator on the landing and this is the same channel rendered a second way;
 * a backlight that competes with it would leave two things of equal weight
 * reporting one fact, which is the defect the 13 August narrowing was written
 * to stop. Reading as an atmosphere the character sits in, rather than as an
 * indicator of its own, is what keeps the orb the thing that is trusted.
 *
 * The radius is a multiple of the head's height so it scales with whatever
 * avatar is loaded, the same rule the camera framing follows.
 */
const GLOW_RADIUS = 2.7

/** Overridable as `?glow=`, because "not as bright as the orb" is a judgement
 *  about how it looks beside the orb and cannot be reasoned to a number.
 *
 *  **Raised from 0.5, which was invisible.** A slate-grey disc at half opacity
 *  behind a near-black character on a near-black page is present in the buffer
 *  and absent to the eye — indistinguishable from the mesh having failed to
 *  build, which is exactly how it was first reported. A dimmer default is only
 *  restraint if the restraint can be seen. */
function glowOpacity(): number {
  return numberParam('glow', 0.85, 0)
}

/** The world-space box a loaded model actually occupies, as one readable line. */

/** The world-space box a loaded model actually occupies, as one readable line. */
function boundsLine(o: THREE.Object3D | null): string {
  if (!o) return 'no model'
  const box = new THREE.Box3().setFromObject(o)
  if (box.isEmpty()) return 'empty'
  const size = box.getSize(new THREE.Vector3())
  const f = (v: THREE.Vector3) => `[${v.x.toFixed(3)}, ${v.y.toFixed(3)}, ${v.z.toFixed(3)}]`
  return `min ${f(box.min)} max ${f(box.max)} size ${f(size)}`
}

interface FacePanel {
  material: THREE.MeshBasicMaterial
  island: UvIsland
  /** Cell currently applied, so a frame that changes nothing costs nothing. */
  applied: number
}

interface RobotAvatarProps {
  px?: number
  src?: string
}

export default function RobotAvatar({ px = 320, src = '/avatars/zaram-robo.glb' }: RobotAvatarProps) {
  const mountRef = useRef<HTMLDivElement | null>(null)
  const stateRef = useRef<EmbodimentState>('idle')
  const [status, setStatus] = useState<'loading' | 'ready' | 'failed'>('loading')
  const [reason, setReason] = useState<string | null>(null)

  const state = useEmbodimentState()
  stateRef.current = state

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    let disposed = false
    let raf = 0
    let root: THREE.Group | null = null
    let mixer: THREE.AnimationMixer | null = null
    let current: THREE.AnimationAction | null = null
    let playing: EmbodimentState | null = null
    let cycleArmed = false
    /** Set when the clips' rig disagreed with the character's, so the fingers
     *  were dropped from every clip and have to be posed instead. */
    let posedFingers = false
    let eyes: FacePanel | null = null
    /** The soft disc behind the character, coloured by state. Built once the
     *  model is measured, because its size and height come from the head. */
    let glow: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshBasicMaterial> | null = null
    let framing = 'not measured'
    /** How many meshes needed a tangent frame computed for them, reported
     *  because a GLB that starts shipping tangents should stop needing this. */
    let tangentsAdded = 0
    let mouth: FacePanel | null = null
    const bags = new Map<EmbodimentState, ShuffleBag<string>>()
    const actions = new Map<string, THREE.AnimationAction>()
    /** Each bone's authored rest rotation, for retargeting clips onto it. */
    const restPose = new Map<string, THREE.Quaternion>()
    const aspectNotes: string[] = []
    const unanimated: string[] = []

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 20)
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setSize(px, px)
    renderer.setPixelRatio(renderScaleFor(window.devicePixelRatio))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    // The character is glossy black with metallic trim, and both are
    // tone-mapping sensitive: without it, specular highlights clip to flat
    // white and the shell reads as plastic.
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 0.88
    mount.appendChild(renderer.domElement)

    // A metal with nothing to reflect renders black. The environment is
    // generated in this process — no image, no fetch, nothing added to the
    // installer — which is what lets the visor and the armour carry reflections
    // without breaking the rule that nothing is downloaded. An .hdr would be
    // several megabytes, and if it were ever fetched rather than bundled it
    // would be a request no gate in this product can see.
    const pmrem = new THREE.PMREMGenerator(renderer)
    const envSource = studioEnvironment()
    const envRT = pmrem.fromEquirectangular(envSource)
    envSource.dispose()
    scene.environment = envRT.texture
    // Slightly under neutral, because the character is glossy black and the
    // environment is what gives black armour its form — too much and the
    // helmet turns silver, which is what happened when this was briefly set to
    // 2.6. That was a misdiagnosis worth recording: the first build showed
    // only a shiny blob, it looked like a black body lost against a black
    // backdrop, and the real cause was a collapsed skeleton hiding everything
    // below the helmet. Brightness was never the problem.
    // **The visor's sheen lives here, and it is the third setting of three.**
    // The environment makes the character *reflective*; the lights make it
    // *bright*; the blur decides whether the reflection resolves into objects.
    // Too low and the faceplate is flat black — dead glass with a sticker on it.
    // Too high and the helmet goes silver and the room's furniture appears in
    // it. Landed by looking: flat at 0.15, recognisable furniture at 0.6 unblurred,
    // silver at 1.1.
    scene.environmentIntensity = envIntensity()

    // Debug only: a flat backdrop makes the silhouette obvious when the
    // question is *where* the model is rather than how it looks.
    const debugBg = new URLSearchParams(window.location.search).get('avatarBg')
    if (debugBg) scene.background = new THREE.Color(debugBg)

    // Above and to the side, not in front. At the inherited (1, 1, 1.5) this
    // sits almost on the camera axis, and on a curved gloss visor that puts a
    // hard white specular streak straight across the face — the one surface
    // whose job is to be read. Moved up and back so the highlight lands on the
    // crown of the helmet instead.
    // **Brightness comes from the lights, not from the environment**, and that
    // split is the whole reason the character can be lit and still wear a black
    // visor. Raising `environmentIntensity` lifts everything the environment
    // touches, and the visor is a near-mirror, so it goes milky long before the
    // armour looks lit — measured on the way here: readable body at 2.0, frosted
    // glass at 3.2. A directional light lands on the armour's diffuse and misses
    // the visor, because the key sits above and to the side precisely so its
    // specular falls on the crown of the helmet instead of the face.
    const lit = lightScale()
    const key = new THREE.DirectionalLight(0xffffff, 1.15 * lit)
    key.position.set(1.3, 1.9, 0.35)
    scene.add(key)
    // A cool fill from the far side, kept low and pushed behind the shoulder
    // line. It exists to separate the arms from the torso on a character that
    // is black on black; anything more frontal than this just adds a second
    // reflection to the visor.
    const fill = new THREE.DirectionalLight(0xa8c0ff, 0.3 * lit)
    fill.position.set(-1.5, 0.7, -0.4)
    scene.add(fill)
    scene.add(new THREE.AmbientLight(0xffffff, 0.34 * lit))
    const rimGain = rimScale()
    const rim = new THREE.DirectionalLight(RIM_COLOUR.idle, 2.2 * rimGain)
    rim.position.set(-1.4, 0.6, -1)
    scene.add(rim)

    // Same two-layer policy as the VRM path: a glTF's buffers and images may
    // carry a `uri` the loader fetches, and that request is invisible to both
    // `EgressGate` (which sees the backend) and `check-no-remote-assets`
    // (which scans source). Inspect before parsing; blank anything the scan
    // did not recognise, during parse.
    const parseManager = new THREE.LoadingManager()
    parseManager.setURLModifier((url) => {
      if (url.startsWith('data:') || url.startsWith('blob:')) return url
      // eslint-disable-next-line no-console
      console.warn(`[embodiment] refused an external avatar resource: ${url}`)
      return 'data:application/octet-stream;base64,'
    })

    const clock = new THREE.Clock()
    let blinkAt = 2 + Math.random() * 3
    const [gapMin, gapMax] = smileGap()
    let smileAt = gapMin + Math.random() * (gapMax - gapMin)
    let smileFor = 0
    const rimTarget = new THREE.Color()

    // ----------------------------------------------------------------- face

    /** Point a panel's emissive map at one atlas cell.
     *
     *  Snapped, never eased. There is no meaningful value between two cells: a
     *  partial offset samples across the boundary and renders half of one
     *  mouth beside half of another. */
    const showCell = (panel: FacePanel | null, index: number) => {
      if (!panel || index < 0 || panel.applied === index) return
      const { repeat, offset } = transformForCell(index)
      const map = panel.material.map
      if (!map) return
      map.repeat.copy(repeat)
      map.offset.copy(offset)
      panel.applied = index
    }

    const adoptAtlas = (panel: FacePanel, url: string) => {
      new THREE.TextureLoader().load(url, (tex) => {
        if (disposed) return
        // glTF puts v=0 at the top row of pixels and `GLTFLoader` sets
        // `flipY = false` to match. A texture loaded separately defaults to
        // `true`, so without this the face renders upside down — and an
        // inverted dot grid is symmetric enough to look merely wrong rather
        // than obviously flipped.
        tex.flipY = false
        tex.colorSpace = THREE.SRGBColorSpace
        // The eye patch's UV island reaches -0.0025. Under default wrapping
        // that sub-pixel sliver samples the far edge of the atlas — a stray
        // column of a neighbouring expression at the panel's edge. Clamping
        // resolves it to the cell's own edge, which is black.
        tex.wrapS = THREE.ClampToEdgeWrapping
        tex.wrapT = THREE.ClampToEdgeWrapping
        tex.anisotropy = renderer.capabilities.getMaxAnisotropy()
        tex.minFilter = THREE.LinearMipmapLinearFilter
        tex.magFilter = THREE.LinearFilter
        tex.generateMipmaps = true
        panel.material.map = tex
        panel.material.needsUpdate = true
        panel.applied = -1
      })
    }

    const preparePanel = (mesh: THREE.Mesh, atlas: string): FacePanel | null => {
      const exported = mesh.material as THREE.MeshStandardMaterial
      const island = uvIslandOf(mesh.geometry)
      if (!island) return null

      // **Replaced with an unlit material, because an LED is not a lit
      // surface.** The exported panels are `MeshStandardMaterial`, which means
      // they take the key light, the fill, the ambient and the environment
      // reflection like any other piece of the model — so the panel reads as a
      // faintly shiny rectangle sitting on the visor, visible well outside the
      // dots it is supposed to be showing. No amount of blackening the base
      // colour removes that, because the reflection is not the base colour.
      //
      // A basic material has no lighting term at all: what it outputs is the
      // texture, and nothing else. Combined with additive blending, black is
      // mathematically absent rather than merely dark, which is exactly how a
      // real emissive display behaves against its own bezel.
      const material = new THREE.MeshBasicMaterial({
        name: exported.name,
        color: 0xffffff,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        toneMapped: false,
      })
      mesh.material = material
      exported.dispose()
      // Report how square a texel lands on this patch. A face whose island
      // does not match its patch's proportions renders a stretched dot grid,
      // which looks like a bad sprite rather than like a UV problem — so it is
      // measured at load and named, with the fix pointed at.
      mesh.geometry.computeBoundingBox()
      const size = mesh.geometry.boundingBox?.getSize(new THREE.Vector3())
      if (size) {
        const [w, h] = [size.x, size.y, size.z].sort((a, b) => b - a)
        const ratio = texelAspect(island, w, h, ATLAS_W, ATLAS_H)
        if (Number.isFinite(ratio) && Math.abs(ratio - 1) > 0.06) {
          aspectNotes.push(
            `${material.name} texels are ${ratio.toFixed(2)}:1 ` +
              `(${ratio > 1 ? 'stretched vertically' : 'stretched horizontally'}; ` +
              'fit its UV island to the full cell — see public/avatars/face/uv_guide.json)',
          )
        }
      }

      const panel: FacePanel = { material, island, applied: -1 }
      adoptAtlas(panel, atlas)
      return panel
    }

    // ------------------------------------------------------------ animation

    const playFor = (s: EmbodimentState, fade: number) => {
      const name = bags.get(s)?.next()
      const next = name ? actions.get(name) : undefined
      // No clip for this state: hold whatever is playing rather than snapping
      // to rest. A missing export is a gap in the asset set, not a reason for
      // the body to drop.
      if (!next) { playing = s; return }
      // A variant may already be running — cycling within a state crossfades
      // from one clip to another, so it has to start from zero rather than
      // resume wherever it was left.
      next.reset().setLoop(THREE.LoopRepeat, Infinity).setEffectiveWeight(1).play()
      if (current && current !== next) current.crossFadeTo(next, fade, false)
      else next.fadeIn(fade)
      current = next
      playing = s
      cycleArmed = false
    }

    /**
     * Move to another variant of the state already playing.
     *
     * **Started before the clip ends, not at the loop point.** A crossfade
     * begun on the loop boundary has to blend a clip's last pose into another
     * clip's first, and those rarely agree — the join reads as a stumble. Begun
     * a fade-length early, the outgoing clip is still mid-motion and the two
     * overlap through a part of the cycle where both are moving, which is what
     * makes the change invisible.
     *
     * With a shuffle bag behind it, the next variant is never the one just
     * playing, so a state held for a long time keeps changing rather than
     * looping the same ten seconds.
     */
    const cycleVariant = () => {
      const s = playing
      if (!s || !current) return
      if ((bags.get(s)?.size ?? 0) < 2) return
      playFor(s, VARIANT_FADE_SECONDS)
    }

    /**
     * Find a bone by its unqualified name, whatever namespace it carries.
     *
     * **The separator is gone by the time this runs, and that is the whole
     * reason this is not a string equality.** `GLTFLoader` passes every node
     * name through `PropertyBinding.sanitizeNodeName`, which *deletes* the
     * characters `[ ] . : /` rather than replacing them — so Maya's
     * `Robot_All_01:Head` arrives as `Robot_All_01Head`, with no separator left
     * to split on. The first version of this matched on `':head'` and could
     * never hit; it failed silently into the fallback camera constants, and the
     * only reason it was caught is that the load log prints the measured span
     * beside the values it fell back to.
     *
     * The preceding-character check keeps `Forehead` from matching `head`: a
     * sanitised namespace ends in a digit or underscore, never a lowercase
     * letter, so requiring a non-letter boundary costs nothing and removes the
     * one plausible false positive.
     */
    const findBone = (o: THREE.Object3D, needle: string): THREE.Object3D | undefined => {
      let hit: THREE.Object3D | undefined
      o.traverse((n) => {
        if (hit) return
        const nm = n.name.toLowerCase()
        if (!nm.endsWith(needle)) return
        const before = nm[nm.length - needle.length - 1]
        if (before === undefined || !/[a-z]/.test(before)) hit = n
      })
      return hit
    }

    // ----------------------------------------------------------------- load

    function onLoaded(gltf: { scene: THREE.Group }) {
      if (disposed) return
      root = gltf.scene
      root.traverse((o) => { o.frustumCulled = false })
      const filtered = applyTextureFiltering(root, renderer.capabilities.getMaxAnisotropy())

      // Face panels are found by *material* name, not object name: the material
      // is what a texture transform applies to, and matching loosely means a
      // rename in Maya produces a warning here rather than a silently dead face.
      root.traverse((o) => {
        const mesh = o as THREE.Mesh
        const mat = mesh.material as THREE.Material | undefined
        if (!(mesh as THREE.Mesh).isMesh || !mat || Array.isArray(mat)) return
        const name = (mat.name || '').toLowerCase()
        if (!eyes && name.includes('eye')) eyes = preparePanel(mesh, '/avatars/face/eyes_atlas_3x3_alpha.png')
        else if (!mouth && name.includes('mouth')) mouth = preparePanel(mesh, '/avatars/face/mouth_atlas_3x3_alpha.png')
      })

      // Dull the shell without touching the faceplate. Multiplicative, so the
      // material's own variation survives — see `roughnessBoost`.
      const boost = roughnessBoost()
      const normal = normalStrength()
      root.traverse((o) => {
        const mesh = o as THREE.Mesh
        const mat = mesh.material as THREE.MeshStandardMaterial | undefined
        if (!mesh.isMesh || !mat || Array.isArray(mat)) return
        if (typeof mat.roughness === 'number') mat.roughness *= boost
        // `normalScale` is a Vector2 — one component per tangent axis — and
        // scaling both equally is the only form that does not skew the surface.
        if (mat.normalScale) mat.normalScale.set(normal, normal)
      })

      // **Tangents, because without them a normal map seams at every UV island
      // edge.**
      //
      // This GLB ships POSITION, NORMAL, TEXCOORD_0, JOINTS_0 and WEIGHTS_0 —
      // and no TANGENT. When the attribute is absent three.js falls back to
      // deriving a tangent frame per fragment from screen-space derivatives of
      // position and UV, which is continuous *within* a UV island and
      // discontinuous *across* one. The two sides of a seam then perturb their
      // normals in different frames, and the join lights differently: a hairline
      // of wrong shading tracing every island border, which on this character
      // runs down both sides of the face.
      //
      // Computing them per vertex puts the frame on the mesh instead of on the
      // screen, so it is the same on both sides of a seam. It is not free of
      // error — Blender bakes against MikkTSpace and this is three's own
      // solver, so the frames differ slightly — but a small constant difference
      // across a whole surface is invisible, while a discontinuity at a line is
      // exactly what the eye is built to find.
      //
      // Guarded rather than assumed: `computeTangents` needs indexed geometry
      // with normals and UVs, and throws a console error without them.
      root.traverse((o) => {
        const mesh = o as THREE.Mesh
        if (!mesh.isMesh) return
        const g = mesh.geometry
        if (!g?.index || !g.attributes.normal || !g.attributes.uv) return
        if (g.attributes.tangent) return
        g.computeTangents()
        tangentsAdded++
      })

      scene.add(root)

      // Frame the head from the *geometry*, not from the skeleton.
      //
      // The VRM path hardcodes a 1.08m camera distance and reads the head bone
      // for height, and its own comment says why the height is derived:
      // "avatars differ in scale and a hardcoded camera puts a short one out of
      // frame". It fixed half the problem. The distance stayed fixed, and more
      // importantly the head *bone* is not the head — on this character it sits
      // at the base of the helmet, with 0.44m of geometry above it out of a
      // 2.0m model. Framing on the bone pointed the camera at its chest.
      //
      // So: the head bone gives the bottom of the head region, the model's
      // bounding box gives the top, and the distance follows from wanting that
      // span to fill a fixed fraction of the view. A human avatar, whose skull
      // rises a little above its head bone, frames correctly by the same rule.
      const head = findBone(root, 'head')
      const hips = findBone(root, 'hips')
      const box = new THREE.Box3().setFromObject(root)
      const headBase = new THREE.Vector3(0, 1.35, 0)
      head?.getWorldPosition(headBase)

      let span = REFERENCE_SPAN
      if (head && hips) {
        const p = new THREE.Vector3()
        hips.getWorldPosition(p)
        if (headBase.y - p.y > 0.05) span = headBase.y - p.y
      }

      const headTop = box.isEmpty() ? headBase.y + 0.25 * (span / REFERENCE_SPAN) : box.max.y
      const headHeight = Math.max(headTop - headBase.y, 0.12 * (span / REFERENCE_SPAN))
      const centreY = headBase.y + 0.30 * headHeight
      // How much of the vertical view the head should occupy. Head-and-
      // shoulders: enough that the face carries the state, with room for the
      // body language underneath it to read.
      const HEAD_FRACTION = frameFraction()
      const fov = THREE.MathUtils.degToRad(camera.fov)
      const dist = headHeight / HEAD_FRACTION / (2 * Math.tan(fov / 2))
      camera.position.set(0, centreY, dist)
      camera.lookAt(0, centreY, 0)
      framing = `head ${headBase.y.toFixed(3)}-${headTop.toFixed(3)}m (${headHeight.toFixed(3)}m), centre ${centreY.toFixed(3)}m, camera z ${dist.toFixed(3)}m`

      // The state glow, behind the character and facing the camera.
      //
      // Sized and placed off the measured head rather than off constants, the
      // same rule the camera follows, so an avatar of another scale gets a glow
      // in proportion instead of a halo or a dot. Behind the model's own depth
      // so it never washes over the shell — additive blending on top of the
      // character would lift the black armour and cost the silhouette.
      // **Sized to fit the frustum, not only to the head, because the canvas is
      // the thing that was cutting it.**
      //
      // A radius derived from the head alone is framing-independent in world
      // units and emphatically not in *view* units: at the shipped framing the
      // disc is wider than the visible box, so the falloff never reaches zero on
      // screen and the viewer sees it stop at a straight vertical line down each
      // side. It reads as a rectangle behind the character — which is exactly
      // what it looked like, and it is a clipping artefact rather than anything
      // wrong with the gradient.
      //
      // So take whichever is smaller: the head-relative size, or what actually
      // fits. The margin can be small because the falloff reaches *exactly* zero
      // at the inscribed circle — there is no residue to cut — and every pixel of
      // slack is glow the viewer does not get.
      const glowZ = box.isEmpty() ? -0.4 : box.min.z - headHeight * GLOW_RADIUS * 0.25
      const glowHalfExtent = Math.tan(fov / 2) * (dist - glowZ) * 0.98
      const glowRadius = Math.min(headHeight * GLOW_RADIUS, glowHalfExtent)
      glow = new THREE.Mesh(
        new THREE.PlaneGeometry(glowRadius * 2, glowRadius * 2),
        new THREE.MeshBasicMaterial({
          map: glowTexture(),
          transparent: true,
          depthWrite: false,
          // **Depth-tested, and it has to be.** Transparent objects draw after
          // opaque ones, so with the test off the glow paints straight over the
          // character it is supposed to be behind — the chest went hazy and the
          // armour lost its black. Tested against the depth the character has
          // already written, it is occluded exactly where the character is,
          // which is what "behind" means. It still writes no depth of its own,
          // so it occludes nothing.
          depthTest: true,
          // **Normal, not additive, and the canvas is why.** The renderer draws
          // on a transparent canvas that the landing composites over its own
          // background, and additive blending contributes colour without ever
          // building alpha — so an additive glow is mathematically present and
          // completely invisible to the page behind it. It looked like the mesh
          // had failed to build.
          blending: THREE.NormalBlending,
          toneMapped: false,
          opacity: glowOpacity(),
        }),
      )
      // Below the head's own centre, so it reads as light behind the character
      // rather than as a halo around its helmet. Centred on the head it looked
      // like a saint; dropped towards the chest it looks like the character is
      // standing in front of something.
      glow.position.set(0, centreY - headHeight * 0.55, glowZ)
      glow.renderOrder = -1
      scene.add(glow)

      // Captured before a single clip plays, because that is the only moment
      // the skeleton is still in its authored rest pose — once an action runs,
      // these values are whatever the animation left behind.
      root.traverse((o) => {
        if ((o as THREE.Bone).isBone) restPose.set(o.name, o.quaternion.clone())
      })



      mixer = new THREE.AnimationMixer(root)
      void loadClips(filtered, span)
    }

    async function loadClips(filtered: number, span: number) {
      let manifest: AnimationManifest | null = null
      try {
        const res = await fetch('/avatars/animations/animations.json')
        manifest = res.ok ? ((await res.json()) as AnimationManifest) : null
      } catch {
        manifest = null
      }

      let trackNote = 'no clips'
      let restReport = ''
      const loaded: string[] = []
      const failed: string[] = []
      // Debug only: `?noAnim=1` loads the character and plays nothing, which
      // separates "the model is wrong" from "the animation is deforming it".
      const noAnim = new URLSearchParams(window.location.search).has('noAnim')
      if (manifest && mixer && !noAnim) {
        const loader = new GLTFLoader(parseManager)
        for (const entry of manifest.clips) {
          const name = clipNameOf(entry)
          try {
            const url = `/avatars/animations/${entry.file}`
            const res = await fetch(url)
            if (!res.ok) { failed.push(entry.file); continue }
            const data = await res.arrayBuffer()
            // **A clip is an avatar file and gets the avatar file's rule.** It
            // is the same format arriving through the same door, and a glTF's
            // `buffers` and `images` carry a `uri` the loader will fetch —
            // invisible to `EgressGate`, which sees the backend, and to
            // `check-no-remote-assets`, which scans source. A beacon is no less
            // a beacon for living in an animation rather than a character.
            const verdict = inspectAvatar(data)
            if (!verdict.ok) {
              failed.push(entry.file)
              // eslint-disable-next-line no-console
              console.warn(`[embodiment] refused ${url}: ${verdict.reason}`, verdict.external)
              continue
            }
            const gltf = await loader.parseAsync(data, '')
            const source = gltf.scene
            // **Named, never `[0]`.** A clip file can carry more than one
            // animation, and the export tool's leftovers sort ahead of the one
            // that was asked for: these files shipped `Armature|Take 001|BaseLayer`
            // first and the retargeted clip last, so reading index zero played
            // the raw un-retargeted take and put the character back in a T-pose
            // with every other number looking right. The manifest names the clip
            // and the exporter names the action after it; match on that, and
            // fall back to the only animation present when there is exactly one.
            const clip =
              gltf.animations.find((a) => a.name === name) ??
              (gltf.animations.length === 1 ? gltf.animations[0] : undefined)
            if (!clip) {
              failed.push(entry.file)
              // eslint-disable-next-line no-console
              console.warn(
                `[embodiment] ${entry.file} has no animation named "${name}": ` +
                  `${gltf.animations.map((a) => a.name).join(', ') || 'none'}`,
              )
              continue
            }
            clip.name = name
            // **Rotation only, and this is the difference between a character
            // and a puddle.** The first build kept every track and dropped
            // only the hips' translation; the result was the entire body
            // collapsed into a lump the size of its own helmet, while the
            // model rendered perfectly with animation disabled.
            //
            // The cause is that Maya exported position and scale curves for
            // all 65 joints, and those values are in the rig's own authoring
            // units — while the GLB's bones sit under an armature carrying a
            // 0.01 scale to convert centimetres to metres. Applied directly,
            // every joint is yanked a hundred times too far from its parent.
            //
            // A skeleton needs none of them. Bone lengths come from the rest
            // pose and animation is rotation; the only translation that ever
            // means anything is the root's, and that is root motion, which a
            // camera locked to the head must not have anyway. Enforced here
            // rather than asked for at export, because an export setting is a
            // thing someone has to remember every time.
            // Does this clip's rig agree with the character's about rest pose?
            //
            // When the two files come out of the same tool the answer is yes,
            // every offset is identity, and none of the correction below is
            // needed — clips play exactly as authored, fingers included. When
            // they do not agree, retargeting is approximate and the finger
            // chains are where it fails worst, so they get dropped and posed.
            //
            // Measured rather than assumed, so that fixing the export pipeline
            // is all it takes: re-export the animations through the same
            // Blender file as the character and this branch flips on its own.
            let worstRest = 0
            for (const t of clip.tracks) {
              const boneName = t.name.slice(0, t.name.lastIndexOf('.'))
              const glbRest = restPose.get(boneName)
              const fbxBone = source.getObjectByName(boneName)
              if (glbRest && fbxBone) worstRest = Math.max(worstRest, glbRest.angleTo(fbxBone.quaternion))
            }
            const rigsAgree = worstRest < RIG_MATCH_TOLERANCE

            const before = clip.tracks.length
            clip.tracks = clip.tracks.filter(
              (t) => t.name.endsWith('.quaternion') && (rigsAgree || !FINGER_BONE.test(t.name)),
            )
            trackNote =
              `${clip.tracks.length}/${before} tracks kept (rotation` +
              `${rigsAgree ? ', fingers included' : ', fingers dropped — rest poses disagree'})`
            posedFingers = !rigsAgree

            // A clip's rotations are *local to the parent*, so they only
            // transfer between two rigs whose rest poses agree. These two do
            // not necessarily: the character travelled Maya -> FBX -> Blender
            // -> glTF and Blender rewrites bone rest orientation on import,
            // while these clips come straight from Maya to the browser. Same
            // joint names, different rest frames, and the visible result is a
            // skeleton tied in a knot. Compare a few bones and say so, rather
            // than leaving it to be inferred from a lump on screen.
            // Retarget each track onto this rig's own rest pose.
            //
            // Measured on the shipped assets: `Hips` rest differs by 88.5deg
            // between the two files, `LeftArm` by 74.5deg, `Spine` by 1.0 and
            // `Head` by 3.2. The hips figure is the Y-up/Z-up conversion, but
            // the others are not the same angle, so a single root correction
            // cannot work — Blender reoriented some bones on import and left
            // others alone, and the clip's rotations are local to whichever
            // frame their bone had at authoring time.
            //
            // The correction is per bone and constant in time: express each
            // key as a rotation *away from the FBX rest*, then re-apply it
            // from the glTF rest. Anything the two files already agree about
            // passes through untouched, so this costs nothing where it is not
            // needed.
            // The offset has to be applied on **both** sides, and the first
            // version of this only did one.
            //
            // A bone's local rotation is expressed in its parent's frame and
            // acts on its own. When the two rigs disagree about either frame,
            // correcting only on the left fixes bones whose rest barely
            // differs and leaves the rest visibly wrong — measured here as
            // `Spine` off by 1 degree and `LeftArm` by 74.5, and on screen as
            // a character whose head and torso animated correctly while its
            // arms stayed pinned in a T-pose.
            //
            // So: `inverse(C_parent) * q * C_bone`, where each `C` is that
            // bone's own rest difference between the two files. Bones the two
            // rigs already agree about get an identity on both sides and pass
            // through unchanged.
            // **This is a partial fix and it is worth being plain about that.**
            // Three standard forms were tried against these assets and none is
            // correct: pre-multiplying by the rest offset (below) animates the
            // torso and head properly and leaves the arms pinned in a T-pose;
            // correcting on both sides with the parent's offset collapses the
            // mesh entirely; post-multiplying rotates the head wrongly. The
            // form kept here is the least wrong of the three.
            //
            // Runtime retargeting between two rigs baked by different tools is
            // not reliably solvable this way, and the real fix is upstream: run
            // the animation FBXs through the *same* Blender file that produced
            // the character, so the rest poses match and no correction is
            // needed at all. This code then becomes a no-op — every bone's
            // offset is identity and every track passes through untouched — so
            // it costs nothing to leave in for avatars that do need it.
            let retargeted = 0
            for (const t of clip.tracks) {
              const boneName = t.name.slice(0, t.name.lastIndexOf('.'))
              const glbRest = restPose.get(boneName)
              const fbxBone = source.getObjectByName(boneName)
              if (!glbRest || !fbxBone) continue
              if (glbRest.angleTo(fbxBone.quaternion) < 1e-3) continue
              const correction = glbRest.clone().multiply(fbxBone.quaternion.clone().invert())
              const values = (t as THREE.QuaternionKeyframeTrack).values
              const q = new THREE.Quaternion()
              for (let i = 0; i < values.length; i += 4) {
                q.set(values[i], values[i + 1], values[i + 2], values[i + 3])
                q.premultiply(correction)
                values[i] = q.x; values[i + 1] = q.y; values[i + 2] = q.z; values[i + 3] = q.w
              }
              retargeted++
            }
            if (!restReport) restReport = `${retargeted}/${clip.tracks.length} tracks retargeted onto the glTF rest pose`

            // Bones the clip says nothing about keep their bind pose forever.
            // On a mocap capture with no glove that is every finger, and a
            // Mixamo bind pose has them splayed — which reads as the character
            // holding its hands rigidly open rather than as missing data.
            // Named here so the gap is legible instead of looking like a bug
            // in the retargeting above.
            if (!unanimated.length) {
              const driven = new Set(clip.tracks.map((t) => t.name.slice(0, t.name.lastIndexOf('.'))))
              for (const boneName of restPose.keys()) {
                if (!driven.has(boneName)) unanimated.push(boneName)
              }
            }
            actions.set(name, mixer.clipAction(clip))
            loaded.push(name)
          } catch {
            failed.push(entry.file)
          }
        }
        for (const [s, list] of clipsByState(manifest)) {
          const names = list.map(clipNameOf).filter((n) => actions.has(n))
          if (names.length) bags.set(s, new ShuffleBag(names))
        }
      }
      if (disposed) return

      // Printed for the reason the VRM path prints its expression list: a clip
      // that did not survive export, or a face panel whose material was
      // renamed, is otherwise indistinguishable from a bug in this file.
      // eslint-disable-next-line no-console
      console.info(
        `[embodiment] ${src}\n` +
          `  face panels: eyes=${eyes ? 'found' : 'MISSING'} mouth=${mouth ? 'found' : 'MISSING'}\n` +
          `  clips loaded (${loaded.length}): ${loaded.join(', ') || 'none'}\n` +
          `  clips failed: ${failed.join(', ') || 'none'}\n` +
          `  ${trackNote}\n` +
          `  face aspect: ${aspectNotes.join(' | ') || 'both square'}\n` +
          `  tangents computed for ${tangentsAdded} mesh(es) — the GLB ships none\n` +
          `  bones with no track (${unanimated.length}): ${unanimated.slice(0, 12).join(', ') || 'none'}${unanimated.length > 12 ? ', …' : ''}\n` +
          `  rest-pose check: ${restReport || 'not run'}\n` +
          `  states with clips: ${[...bags.keys()].join(', ') || 'none'}\n` +
          `  head-hips span ${span.toFixed(3)}m\n` +
          `  framing: ${framing}\n` +
          // Where the *geometry* is, not where the skeleton says it should be.
          // The two can disagree — a skinned mesh carries its own bind matrices
          // and a root transform can be applied to one and not the other — and
          // when they do, a camera framed off the rig points at empty space.
          `  model bounds: ${boundsLine(root)}\n` +
          `  render buffer: ${px * renderer.getPixelRatio()}px for a ${px}px box, textures filtered: ${filtered}`,
      )
      if (!eyes || !mouth) setReason('The avatar loaded but its face panels were not found.')

      // Only when the clips could not be trusted with them. If the rigs agree
      // the mocap's own finger motion is playing and posing over it would
      // throw away real data.
      if (posedFingers && root) {
        const curl = fingerCurl()
        root.traverse((o) => {
          if (!FINGER_BONE.test(o.name)) return
          // The middle and distal phalanges curl further than the knuckle,
          // which is the difference between a relaxed hand and a flat one.
          const joint = Number(o.name.slice(-1)) || 1
          o.rotation.z += curl * (joint >= 2 ? 1.4 : 1)
        })
      }

      playFor(stateRef.current, 0)
      setStatus('ready')
    }

    function onLoadError(err: unknown) {
      if (disposed) return
      setStatus('failed')
      setReason(err instanceof Error ? err.message : 'The avatar file could not be read.')
    }

    const bytes = new THREE.FileLoader()
    bytes.setResponseType('arraybuffer')
    bytes.load(
      src,
      (data) => {
        if (disposed) return
        const verdict = inspectAvatar(data as ArrayBuffer)
        if (!verdict.ok) {
          setStatus('failed')
          setReason(verdict.reason)
          // eslint-disable-next-line no-console
          console.warn(`[embodiment] refused ${src}: ${verdict.reason}`, verdict.external)
          return
        }
        new GLTFLoader(parseManager).parse(data as ArrayBuffer, '', onLoaded, onLoadError)
      },
      undefined,
      (err) => {
        if (disposed) return
        setStatus('failed')
        setReason(err instanceof Error ? err.message : 'The avatar file could not be read.')
      },
    )

    // ---------------------------------------------------------------- frame

    const tick = () => {
      raf = requestAnimationFrame(tick)
      const dt = clock.getDelta()
      const now = clock.elapsedTime
      const s = stateRef.current

      const k = approachRate(dt, RIM_EASE_SECONDS)
      rimTarget.setHex(RIM_COLOUR[s])
      rim.color.lerp(rimTarget, k)
      rim.intensity = THREE.MathUtils.lerp(rim.intensity, (s === 'swapping' ? 1.1 : 2.2) * rimGain, k)
      // The glow rides the same eased colour as the rim, off the same table, so
      // the two can never disagree about what state the system is in. Dimmer
      // while swapping for the same reason the rim is: a swap is the one state
      // that should read as the character receding rather than working.
      if (glow) {
        glow.material.color.copy(rim.color)
        glow.material.opacity = THREE.MathUtils.lerp(
          glow.material.opacity,
          s === 'swapping' ? glowOpacity() * 0.5 : glowOpacity(),
          k,
        )
      }

      // A state change draws a fresh variant, so returning to idle after a
      // reply is a different idle than the one before it.
      if (playing !== null && playing !== s) playFor(s, CLIP_FADE_SECONDS)
      else if (current && !cycleArmed) {
        // Arm the next variant a fade-length before this one ends, so the
        // blend spans the loop point instead of landing on it.
        const clip = current.getClip()
        if (clip.duration > VARIANT_FADE_SECONDS * 2 &&
            current.time > clip.duration - VARIANT_FADE_SECONDS) {
          cycleArmed = true
          cycleVariant()
        }
      }
      mixer?.update(dt)

      // Run the idle expression before the eyes, because both halves of the
      // face wear it and the eyes are drawn first.
      let smiling = false
      if (s === 'idle') {
        // The timer is reset on the way out rather than paused: a smile
        // half-finished when a reply arrives should not be waiting to resume
        // over the answer.
        smileAt -= dt
        if (smileAt <= 0) {
          smileFor = SMILE_SECONDS
          smileAt = gapMin + Math.random() * (gapMax - gapMin)
        }
        if (smileFor > 0) {
          smileFor -= dt
          smiling = true
        }
      } else {
        smileFor = 0
      }

      blinkAt -= dt
      const blinking = blinkAt < 0.12
      if (blinkAt < 0) blinkAt = 2.5 + Math.random() * 3.5
      showCell(
        eyes,
        EYE_CELLS.indexOf(smiling ? 'happy' : blinking ? 'blink' : EYES_FOR_STATE[s]),
      )

      // Lip sync runs off Kokoro's own phoneme timings scrubbed against
      // playback position, not a cycle — `audio.currentTime` is the clock,
      // because an elapsed counter drifts the moment audio buffers.
      const { audio, track } = useSpeechStore.getState()
      let shape: MouthCell = 'sil'
      if (s === 'speaking' && audio && track.length > 0) shape = visemeAt(track, audio.currentTime)
      else if (s === 'speaking') shape = Math.sin(now * 9) > 0 ? 'aa' : 'ih'
      else if (smiling) shape = 'smile'
      showCell(mouth, MOUTH_CELLS.indexOf(shape))

      renderer.render(scene, camera)
    }
    tick()

    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      mixer?.stopAllAction()
      root?.traverse((o) => {
        const m = o as THREE.Mesh
        if (m.geometry) m.geometry.dispose()
        const mat = m.material
        for (const one of Array.isArray(mat) ? mat : mat ? [mat] : []) one.dispose()
      })
      envRT.dispose()
      pmrem.dispose()
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
    }
  }, [px, src])

  return (
    <div style={{ width: px, height: px, position: 'relative' }}>
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
