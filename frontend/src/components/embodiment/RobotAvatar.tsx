import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { useEmbodimentState, type EmbodimentState } from '@/hooks/useEmbodimentState'
import { useSpeechStore } from '@/stores/speechStore'
import { visemeAt, type Viseme } from '@/lib/visemes'
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
  const raw = Number(new URLSearchParams(window.location.search).get('fingerCurl'))
  return Number.isFinite(raw) && raw !== 0 ? raw : 0.32
}

/** Atlas dimensions, needed to turn UV spans into texel counts. */
const ATLAS_W = 768
const ATLAS_H = 512

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
  const raw = Number(new URLSearchParams(window.location.search).get('headFraction'))
  return raw > 0.02 && raw <= 1 ? raw : 0.5
}

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
    let framing = 'not measured'
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

    // A metal with nothing to reflect renders black. `RoomEnvironment` is
    // generated from geometry in this process — no image, no fetch, nothing
    // added to the installer — which is what lets the visor and the armour
    // carry reflections without breaking the rule that nothing is downloaded.
    // An .hdr would be several megabytes, and if it were ever fetched rather
    // than bundled it would be a request no gate in this product can see.
    const pmrem = new THREE.PMREMGenerator(renderer)
    const envRT = pmrem.fromScene(new RoomEnvironment(), 0.04)
    scene.environment = envRT.texture
    // Slightly under neutral, because the character is glossy black and the
    // environment is what gives black armour its form — too much and the
    // helmet turns silver, which is what happened when this was briefly set to
    // 2.6. That was a misdiagnosis worth recording: the first build showed
    // only a shiny blob, it looked like a black body lost against a black
    // backdrop, and the real cause was a collapsed skeleton hiding everything
    // below the helmet. Brightness was never the problem.
    scene.environmentIntensity = 0.32

    // Debug only: a flat backdrop makes the silhouette obvious when the
    // question is *where* the model is rather than how it looks.
    const debugBg = new URLSearchParams(window.location.search).get('avatarBg')
    if (debugBg) scene.background = new THREE.Color(debugBg)

    // Above and to the side, not in front. At the inherited (1, 1, 1.5) this
    // sits almost on the camera axis, and on a curved gloss visor that puts a
    // hard white specular streak straight across the face — the one surface
    // whose job is to be read. Moved up and back so the highlight lands on the
    // crown of the helmet instead.
    const key = new THREE.DirectionalLight(0xffffff, 1.15)
    key.position.set(1.3, 1.9, 0.35)
    scene.add(key)
    // A cool fill from the far side, kept low and pushed behind the shoulder
    // line. It exists to separate the arms from the torso on a character that
    // is black on black; anything more frontal than this just adds a second
    // reflection to the visor.
    const fill = new THREE.DirectionalLight(0xa8c0ff, 0.3)
    fill.position.set(-1.5, 0.7, -0.4)
    scene.add(fill)
    scene.add(new THREE.AmbientLight(0xffffff, 0.34))
    const rim = new THREE.DirectionalLight(RIM_COLOUR.idle, 2.2)
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
        if (!eyes && name.includes('eye')) eyes = preparePanel(mesh, '/avatars/face/eyes_atlas_3x2_alpha.png')
        else if (!mouth && name.includes('mouth')) mouth = preparePanel(mesh, '/avatars/face/mouth_atlas_3x2_alpha.png')
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
      rim.intensity = THREE.MathUtils.lerp(rim.intensity, s === 'swapping' ? 1.1 : 2.2, k)

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

      blinkAt -= dt
      const blinking = blinkAt < 0.12
      if (blinkAt < 0) blinkAt = 2.5 + Math.random() * 3.5
      showCell(eyes, EYE_CELLS.indexOf(blinking ? 'blink' : EYES_FOR_STATE[s]))

      // Lip sync runs off Kokoro's own phoneme timings scrubbed against
      // playback position, not a cycle — `audio.currentTime` is the clock,
      // because an elapsed counter drifts the moment audio buffers.
      const { audio, track } = useSpeechStore.getState()
      let shape: Viseme = 'sil'
      if (s === 'speaking' && audio && track.length > 0) shape = visemeAt(track, audio.currentTime)
      else if (s === 'speaking') shape = Math.sin(now * 9) > 0 ? 'aa' : 'ih'
      showCell(mouth, MOUTH_CELLS.indexOf(shape as MouthCell))

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
