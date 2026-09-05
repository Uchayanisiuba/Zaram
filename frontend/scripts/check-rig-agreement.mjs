/**
 * Do the shipped animation clips and the character agree about rest pose?
 *
 * **This reads the glTF files themselves, and that is the point.** The same
 * question was asked twice before through a tool that answers it wrongly: a
 * Blender-side comparison imports both files first, and Blender's glTF importer
 * re-orients bones on the way in (`bone_heuristic`), so it reports the rest pose
 * Blender chose rather than the one stored in the file. The browser reads node
 * TRS straight out of the JSON chunk, so that is what has to be compared.
 *
 * A clip's rotations are local to whichever rest frame its bones had when it was
 * authored. When the character and the clips disagree about that frame, every
 * rotation means something different on the other rig -- and the visible result
 * is a character whose torso animates while its arms stay pinned in a T-pose.
 * `RobotAvatar` measures this at load and prints it, but a browser reload is a
 * slow way to answer a question about two files on disk.
 *
 * Compares **local** rest rotation per bone, because that is the frame a clip's
 * keys are expressed in and therefore the only comparison that predicts whether
 * the clip will play correctly. World-space agreement is neither necessary nor
 * sufficient.
 *
 *     node scripts/check-rig-agreement.mjs
 *
 * Exits non-zero when they disagree.
 */

import { readFileSync, existsSync, readdirSync } from 'node:fs'
import { join, dirname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const AVATARS = join(HERE, '..', 'public', 'avatars')
const CHARACTER = join(AVATARS, 'zaram-robo.glb')
const CLIPS_DIR = join(AVATARS, 'animations')

/** The same tolerance `RobotAvatar.RIG_MATCH_TOLERANCE` uses, in radians. */
const TOLERANCE = 0.05

/**
 * The JSON chunk of a GLB.
 *
 * Header is magic/version/length as three uint32, then chunks of
 * length/type/data. The first chunk is always JSON per the spec.
 */
function gltfJson(path) {
  const buf = readFileSync(path)
  if (buf.readUInt32LE(0) !== 0x46546c67) throw new Error(`${basename(path)} is not a GLB`)
  const chunkLength = buf.readUInt32LE(12)
  const chunkType = buf.readUInt32LE(16)
  if (chunkType !== 0x4e4f534a) throw new Error(`${basename(path)}: first chunk is not JSON`)
  return JSON.parse(buf.subarray(20, 20 + chunkLength).toString('utf8'))
}

/**
 * Bone names, sanitized the way three.js sanitizes them.
 *
 * `PropertyBinding.sanitizeNodeName` deletes `[].:/ ` outright, so
 * `Robot_All_01:Hips` is addressed in the browser as `Robot_All_01Hips`. Two
 * files can spell the same joint differently and still bind, so comparing raw
 * names reports a perfect match over zero shared bones -- which reads exactly
 * like success.
 */
function sanitize(name) {
  return String(name).replace(/[\s.:[\]/]/g, '').toLowerCase()
}

/** Local rest rotation per bone, keyed by sanitized name. */
function restPose(gltf) {
  const skinned = new Set()
  for (const skin of gltf.skins || []) for (const j of skin.joints) skinned.add(j)
  const out = new Map()
  ;(gltf.nodes || []).forEach((node, i) => {
    if (!skinned.has(i)) return
    // glTF defaults an absent rotation to identity.
    const r = node.rotation || [0, 0, 0, 1]
    out.set(sanitize(node.name ?? `node${i}`), r)
  })
  return out
}

/** Angle between two quaternions, in radians, resolving the double cover. */
function angleBetween(a, b) {
  const dot = Math.abs(a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3])
  return 2 * Math.acos(Math.min(1, dot))
}

function compare(character, clipPath) {
  const clip = restPose(gltfJson(clipPath))
  let worst = 0
  let worstBone = 'none'
  let shared = 0
  let over = 0
  for (const [name, q] of clip) {
    const ref = character.get(name)
    if (!ref) continue
    shared++
    const a = angleBetween(ref, q)
    if (a > TOLERANCE) over++
    if (a > worst) {
      worst = a
      worstBone = name
    }
  }
  return { worst, worstBone, shared, over, total: clip.size }
}

const deg = (r) => ((r * 180) / Math.PI).toFixed(2)

if (!existsSync(CHARACTER)) {
  console.error(`no character at ${CHARACTER}`)
  process.exit(1)
}

const character = restPose(gltfJson(CHARACTER))
console.log(`character: ${character.size} bones (${basename(CHARACTER)})`)

const clips = existsSync(CLIPS_DIR)
  ? readdirSync(CLIPS_DIR).filter((f) => f.endsWith('.glb')).sort()
  : []

if (!clips.length) {
  console.log('no .glb clips to check — the shipped clips are still .fbx')
  process.exit(0)
}

let bad = 0
for (const file of clips) {
  const r = compare(character, join(CLIPS_DIR, file))
  const verdict = r.shared === 0 ? 'NO SHARED BONES' : r.worst < TOLERANCE ? 'agrees' : 'DISAGREES'
  if (verdict !== 'agrees') bad++
  console.log(
    `  ${file}: ${r.shared}/${r.total} bones shared, ` +
      `worst ${deg(r.worst)}deg on ${r.worstBone}, ${r.over} over tolerance — ${verdict}`,
  )
}

if (bad) {
  console.error(`\n${bad} clip(s) disagree with the character's rest pose.`)
  process.exit(1)
}
console.log('\nrest poses agree — clips play as authored, fingers included.')
