import * as THREE from 'three'

/**
 * The LED face: which atlas cell is showing, and how it reaches the geometry.
 *
 * The robot's face is not a blendshape face. Its eyes and mouth are two skinned
 * patches on the visor, each carrying a sprite atlas on `emissiveMap`, and an
 * expression is a **UV window slid across that atlas** rather than a mesh
 * deformation. Two consequences run through this whole file.
 *
 * **Cell selection is `repeat` + `offset`, never a change to the mesh UVs.**
 * The geometry is authored once and never touched again; only the texture
 * transform moves. That is what lets the same patch show six expressions.
 *
 * **A cell is chosen, never blended.** There is no meaningful state between two
 * cells: a half-applied offset samples the seam between them and renders a
 * sliced composite of two mouths. Everything here snaps.
 */

/** Atlas layout. Both atlases are 3x3 cells of 256px, so one cell is a third
 *  of the width and a third of the height. Written as constants rather than
 *  read from the manifest because the *shape* is structural — a manifest that
 *  disagreed would be a broken manifest, not a different layout.
 *
 *  **Grown from 3x2 for the seventh mouth cell.** All six were visemes and
 *  `visemeAt` can emit any of them mid-sentence, so none could be given up for
 *  an expression. A third row costs nothing anywhere else: the cell stays
 *  square, and a mesh's UV island is normalised *inside* its cell, so no island
 *  moved and no patch had to be re-modelled. The eyes carry the third row empty
 *  rather than making the layout per-atlas and threading that through every
 *  caller. */
const COLS = 3
const ROWS = 3
export const CELL_W = 1 / COLS
export const CELL_H = 1 / ROWS

export type EyeCell = 'open' | 'blink' | 'thinking' | 'listening' | 'swapping' | 'warming'
export type MouthCell = 'sil' | 'aa' | 'ih' | 'ou' | 'ee' | 'oh' | 'smile'

/** Cell order within each atlas, top-left to bottom-right *in UV terms*.
 *
 *  Index 0 is the rest state on both atlases, deliberately: it is what shows
 *  when nothing has asked for anything, so a face with no driver attached is a
 *  calm face rather than a garbled one. */
export const EYE_CELLS: EyeCell[] = ['open', 'blink', 'thinking', 'listening', 'swapping', 'warming']
/** `smile` is the one cell here that is not a viseme. It is an idle expression,
 *  never reachable from `visemeAt`, and it lives at the end so the six speech
 *  shapes keep the indices they were authored at. */
export const MOUTH_CELLS: MouthCell[] = ['sil', 'aa', 'ih', 'ou', 'ee', 'oh', 'smile']

/**
 * Where a cell sits in the texture, in glTF UV space.
 *
 * **The vertical flip is the whole reason this function exists.** The atlas was
 * authored for the OpenGL convention, where v=0 is the *bottom* of the image
 * and cell 0 therefore lives in the bottom row of the PNG. glTF inverts that:
 * `GLTFLoader` sets `flipY = false`, so v=0 is the *top* row of pixels. Reading
 * the manifest's offsets straight through would put every rest state on the
 * wrong row — a permanently listening pair of eyes and a permanent `ou` mouth,
 * which looks like a driver bug rather than a coordinate-space bug and would
 * cost an afternoon to find.
 *
 * So the row is flipped here, once, in the one place that knows about it.
 */
export function cellRect(index: number): { x: number; y: number; w: number; h: number } {
  const col = index % COLS
  const row = Math.floor(index / COLS)
  return { x: col * CELL_W, y: (ROWS - 1 - row) * CELL_H, w: CELL_W, h: CELL_H }
}

/** The UV rectangle a mesh's own coordinates actually occupy. */
export interface UvIsland {
  u0: number
  u1: number
  v0: number
  v1: number
}

export function uvIslandOf(geometry: THREE.BufferGeometry): UvIsland | null {
  const uv = geometry.getAttribute('uv')
  if (!uv) return null
  let u0 = Infinity, u1 = -Infinity, v0 = Infinity, v1 = -Infinity
  for (let i = 0; i < uv.count; i++) {
    const u = uv.getX(i), v = uv.getY(i)
    if (u < u0) u0 = u
    if (u > u1) u1 = u
    if (v < v0) v0 = v
    if (v > v1) v1 = v
  }
  if (!(u1 > u0) || !(v1 > v0)) return null
  return { u0, u1, v0, v1 }
}

/**
 * The texture transform that shows one atlas cell on a face patch.
 *
 * **Deliberately a plain cell selection, after a normalising version was tried
 * and reverted.** The mouth patch shipped with a UV island covering only about
 * a quarter of its cell — it had been positioned against `sil`, the thinnest
 * frame in the set — so `aa` and `oh` fell outside it and clipped. Stretching
 * each island to fill its cell removed that clipping and introduced something
 * worse: the cell is square in texels and the patches are not, so every sprite
 * came out warped. The eye patch was undistorted to within 0.5% under the plain
 * transform and 2.8x wrong under the normalising one.
 *
 * Which makes island size a **modelling** property, not something code can
 * paper over. An island that does not span its cell shows part of the sprite;
 * an island whose aspect does not match the patch's stretches it. Both are
 * fixed against `uv_guide.json` and the templates beside it, and
 * `texelAspect` below reports either at load rather than leaving it to be
 * noticed on screen.
 */
export function transformForCell(index: number): {
  repeat: THREE.Vector2
  offset: THREE.Vector2
} {
  const cell = cellRect(index)
  return {
    repeat: new THREE.Vector2(cell.w, cell.h),
    offset: new THREE.Vector2(cell.x, cell.y),
  }
}

/**
 * How far from square one texel lands on a patch — 1.0 is undistorted.
 *
 * Measured rather than assumed because the intuitive check is wrong: comparing
 * world-units-per-UV-unit says the eye patch is square to within 0.5%, and it
 * only says so by accident. UV units are not isotropic on a 768x512 atlas, so
 * the comparison has to be in *texels*, after the cell transform has scaled the
 * island by `repeat`.
 *
 * Returns the horizontal:vertical ratio of texel density. Above 1 means the
 * sprite is squashed horizontally; below 1, stretched.
 */
export function texelAspect(
  island: UvIsland,
  worldWidth: number,
  worldHeight: number,
  atlasWidth: number,
  atlasHeight: number,
): number {
  const uTexels = (island.u1 - island.u0) * CELL_W * atlasWidth
  const vTexels = (island.v1 - island.v0) * CELL_H * atlasHeight
  if (!(worldWidth > 0) || !(worldHeight > 0) || !(vTexels > 0)) return NaN
  return uTexels / worldWidth / (vTexels / worldHeight)
}
