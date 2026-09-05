/**
 * The LED face's coordinate maths, tested because both bugs it encodes were
 * invisible in the code that caused them.
 *
 * One is a coordinate-space flip: the atlas was authored bottom-up and glTF
 * samples top-down, so reading the manifest's offsets literally puts every rest
 * state on the wrong row. The other is a UV island far smaller than the cell it
 * addresses, which silently clips the tallest frames off the mouth. Neither
 * throws, neither logs, and both produce a face that looks broken in a way that
 * points at the driver rather than at the numbers.
 */
import { describe, it, expect } from 'vitest'
// Imported rather than read off disk: Vite resolves JSON at build time, so the
// test needs no Node types, and a manifest that moved or was deleted fails at
// compile rather than at run — which is the failure worth catching early.
import manifest from '../../public/avatars/face/manifest.json'
import { cellRect, transformForCell, texelAspect, uvIslandOf, CELL_W, CELL_H, EYE_CELLS, MOUTH_CELLS } from './faceAtlas'

/** Every cell the layout holds, derived rather than restated. */
const COLS_TIMES_ROWS = Math.round(1 / CELL_W) * Math.round(1 / CELL_H)
import { VISEMES } from './visemes'
import * as THREE from 'three'

describe('cellRect', () => {
  it('puts the rest cell on the bottom row of the PNG, which is the LAST in glTF v', () => {
    // Cell 0 is `sil` / eyes-open. The atlas writes it into the bottom row of
    // the image; glTF's v runs downward from the top, so on a four-row atlas
    // that row begins at v = 3/4. Getting this backwards is the flip described
    // above, and it survives a layout change only because `cellRect` is the one
    // place that knows about it — this assertion has now outlived two of them,
    // 3x2 to 3x3 and 3x3 to 4x4, by being written against `ROWS` rather than a
    // literal.
    expect(cellRect(0)).toEqual({ x: 0, y: 3 * CELL_H, w: CELL_W, h: CELL_H })
  })

  it('fills a PNG row per four cells, bottom row first', () => {
    expect(cellRect(3)).toMatchObject({ x: 3 * CELL_W, y: 3 * CELL_H })
    // Cell 4 starts the next row up.
    expect(cellRect(4)).toMatchObject({ x: 0, y: 2 * CELL_H })
    expect(cellRect(7)).toMatchObject({ x: 3 * CELL_W, y: 2 * CELL_H })
    expect(cellRect(8)).toMatchObject({ x: 0, y: CELL_H })
  })

  it('advances a quarter of the atlas per column', () => {
    expect(cellRect(1).x).toBeCloseTo(1 / 4, 10)
    expect(cellRect(2).x).toBeCloseTo(2 / 4, 10)
  })
})

describe('transformForCell', () => {
  it('selects a cell without rescaling the island', () => {
    // A plain cell selection, and the "without rescaling" is the point. An
    // earlier version stretched each island to fill its cell, which removed a
    // clipping bug on the mouth and warped every sprite instead: the cell is
    // square in texels and the patches are not.
    const t = transformForCell(0)
    expect(t.repeat.x).toBeCloseTo(1 / 4, 10)
    expect(t.repeat.y).toBeCloseTo(1 / 4, 10)
    expect(t.offset.x).toBeCloseTo(0, 10)
    expect(t.offset.y).toBeCloseTo(3 / 4, 10)
  })

  it('maps a full 0-1 island exactly onto its cell, for every cell', () => {
    for (let i = 0; i < COLS_TIMES_ROWS; i++) {
      const t = transformForCell(i)
      const cell = cellRect(i)
      expect(0 * t.repeat.x + t.offset.x).toBeCloseTo(cell.x, 10)
      expect(1 * t.repeat.x + t.offset.x).toBeCloseTo(cell.x + cell.w, 10)
      expect(0 * t.repeat.y + t.offset.y).toBeCloseTo(cell.y, 10)
      expect(1 * t.repeat.y + t.offset.y).toBeCloseTo(cell.y + cell.h, 10)
    }
  })

  it('keeps every cell inside the atlas', () => {
    for (let i = 0; i < COLS_TIMES_ROWS; i++) {
      const t = transformForCell(i)
      expect(t.offset.x).toBeGreaterThanOrEqual(0)
      expect(t.offset.y).toBeGreaterThanOrEqual(0)
      expect(t.offset.x + t.repeat.x).toBeLessThanOrEqual(1 + 1e-9)
      expect(t.offset.y + t.repeat.y).toBeLessThanOrEqual(1 + 1e-9)
    }
  })
})

describe('texelAspect', () => {
  it('reports the shipped eye patch as square', () => {
    // Measured off the GLB: island u -0.0025..0.998, v 0.2937..0.6455 on a
    // patch 0.3044 x 0.1075 in mesh units, against the 768x768 atlas. This is
    // the check that says the eyes were never the problem.
    //
    // The atlas has grown twice and this number has not moved, which is the
    // point: `CELL_H` fell 1/2 -> 1/3 -> 1/4 as the height rose 512 -> 768 ->
    // 1024, so a cell is still 256 texels tall and an island still spans the
    // same fraction of it. Passing the wrong atlas size here reports a ratio
    // that looks like a regression in the modelling.
    const ratio = texelAspect(
      { u0: -0.0025, u1: 0.998, v0: 0.2937, v1: 0.6455 }, 0.3044, 0.1075, 1024, 1024,
    )
    expect(ratio).toBeGreaterThan(0.98)
    expect(ratio).toBeLessThan(1.02)
  })

  it('reports the shipped mouth patch as stretched', () => {
    // Same measurement for the mouth: 29% wider than tall per texel, because
    // its island covers only a quarter of the cell's height. A modelling fix,
    // which is why this is reported rather than corrected.
    const ratio = texelAspect(
      { u0: 0.0559, u1: 0.9318, v0: 0.4336, v1: 0.6799 }, 0.2483, 0.0901, 768, 768,
    )
    expect(ratio).toBeGreaterThan(1.2)
  })

  it('refuses to divide by a degenerate patch', () => {
    expect(texelAspect({ u0: 0, u1: 1, v0: 0, v1: 1 }, 0, 1, 768, 768)).toBeNaN()
  })
})

describe('uvIslandOf', () => {
  it('returns the extent actually used, not the unit square', () => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('uv', new THREE.Float32BufferAttribute([0.2, 0.4, 0.7, 0.9, 0.5, 0.6], 2))
    // Compared approximately because the attribute is Float32 and the literals
    // are Float64 — 0.2 does not survive the round trip exactly, which is a
    // property of the buffer type rather than of this function.
    const island = uvIslandOf(g)
    expect(island?.u0).toBeCloseTo(0.2, 6)
    expect(island?.u1).toBeCloseTo(0.7, 6)
    expect(island?.v0).toBeCloseTo(0.4, 6)
    expect(island?.v1).toBeCloseTo(0.9, 6)
  })

  it('reports nothing for geometry with no UVs, rather than guessing', () => {
    expect(uvIslandOf(new THREE.BufferGeometry())).toBeNull()
  })

  it('reports nothing for a degenerate island that would divide by zero', () => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('uv', new THREE.Float32BufferAttribute([0.5, 0.5, 0.5, 0.5], 2))
    expect(uvIslandOf(g)).toBeNull()
  })
})

describe('the atlas manifest agrees with the code that reads it', () => {

  it('names the same mouth cells, in the same order', () => {
    const byIndex = Object.entries(manifest.atlases.mouth.expressions)
      .sort((a, b) => (a[1] as { index: number }).index - (b[1] as { index: number }).index)
      .map(([name]) => name)
    expect(byIndex).toEqual(MOUTH_CELLS)
  })

  it('names the same eye cells, in the same order', () => {
    const byIndex = Object.entries(manifest.atlases.eyes.expressions)
      .sort((a, b) => (a[1] as { index: number }).index - (b[1] as { index: number }).index)
      .map(([name]) => name)
    expect(byIndex).toEqual(EYE_CELLS)
  })

  it('keeps the smile out of the speech path', () => {
    // `smile` is an idle expression, not a phoneme. If it ever became reachable
    // from `visemeAt` the character would grin mid-word, which is the exact
    // failure the state-derived rule exists to prevent.
    expect(VISEMES).not.toContain('smile')
    expect(MOUTH_CELLS).toContain('smile')
  })

  it('covers every viseme the speech path can emit', () => {
    // `visemeAt` returns one of these for every phoneme Kokoro produces. A
    // mouth cell missing here is a mouth that stops moving mid-sentence.
    for (const v of VISEMES) expect(MOUTH_CELLS).toContain(v)
  })

  it('agrees with the code about cell geometry', () => {
    expect(manifest.repeat[0]).toBeCloseTo(CELL_W, 10)
    expect(manifest.repeat[1]).toBeCloseTo(CELL_H, 10)
  })
})
