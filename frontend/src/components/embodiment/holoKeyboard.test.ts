// @vitest-environment node
/**
 * The coding keyboard: built from lines and panes, shown only while asked for,
 * arriving with a scan and leaving faster, and still for reduced motion. It
 * faces the typist, keeps one size and place however the hands move, and is
 * drawn with nothing beside it -- the mouse was taken out.
 */
import * as THREE from 'three'
import { describe, expect, it } from 'vitest'

import { boardPlacement, createHoloKeyboard, HANDS_ON_BOARD, keyLayout } from './holoKeyboard'

const step = (kb: ReturnType<typeof createHoloKeyboard>, seconds: number, active: boolean, reduced = false) => {
  for (let t = 0; t < seconds; t += 1 / 60) kb.update(1 / 60, t, active, reduced)
}

describe('the board', () => {
  it('has five rows of keys, all inside the board', () => {
    const rows = keyLayout()
    expect(rows).toHaveLength(5)
    for (const k of rows.flat()) {
      expect(Math.abs(k.x) + k.w / 2).toBeLessThan(0.5)
      expect(k.w).toBeGreaterThan(0)
      expect(k.d).toBeGreaterThan(0)
    }
  })

  it('is drawn in the colour it is given, with normal blending so a transparent canvas shows it', () => {
    const kb = createHoloKeyboard(0xa855f7)
    const materials: THREE.Material[] = []
    kb.group.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.Material | undefined
      if (m) materials.push(m)
    })
    expect(materials.length).toBeGreaterThan(5)
    for (const m of materials) expect(m.blending).toBe(THREE.NormalBlending)
    const deck = materials.find((m) => m instanceof THREE.MeshBasicMaterial) as THREE.MeshBasicMaterial
    expect(deck.color.getHex()).toBe(0xa855f7)
  })
})

describe('appearing and leaving', () => {
  it('is hidden until asked for, then fully shown within its spawn time', () => {
    const kb = createHoloKeyboard(0xa855f7, () => 0.9)
    kb.update(1 / 60, 0, false, false)
    expect(kb.group.visible).toBe(false)
    step(kb, 0.35, true)
    expect(kb.shown).toBeGreaterThan(0)
    expect(kb.shown).toBeLessThan(1)
    step(kb, 0.5, true)
    expect(kb.shown).toBe(1)
    expect(kb.group.visible).toBe(true)
  })

  it('leaves faster than it arrives, and is gone when the state ends', () => {
    const kb = createHoloKeyboard(0xa855f7, () => 0.9)
    step(kb, 1, true)
    step(kb, 0.4, false)
    expect(kb.shown).toBe(0)
    expect(kb.group.visible).toBe(false)
  })

  it('shows a scan line only while arriving or leaving', () => {
    const kb = createHoloKeyboard(0xa855f7, () => 0.9)
    const scanVisible = () => {
      let seen = false
      kb.group.traverse((o) => {
        const g = (o as THREE.Mesh).geometry as THREE.BufferGeometry | undefined
        if (o.visible && g instanceof THREE.PlaneGeometry && g.parameters.width > 1) seen = true
      })
      return seen
    }
    step(kb, 0.3, true)
    expect(scanVisible()).toBe(true)
    step(kb, 1, true)
    expect(scanVisible()).toBe(false)
  })

  it('does not flicker, scan or light keys for reduced motion', () => {
    // A random source that would always flicker if flicker were allowed.
    const kb = createHoloKeyboard(0xa855f7, () => 0)
    step(kb, 0.35, true, true)
    const opacities: number[] = []
    kb.group.traverse((o) => {
      const m = (o as THREE.Line).material as THREE.LineBasicMaterial | undefined
      if (o instanceof THREE.LineLoop && m) opacities.push(m.opacity)
    })
    expect(opacities[0]).toBeGreaterThan(0.5)
    step(kb, 2, true, true)
    let lit = 0
    kb.group.traverse((o) => {
      const g = (o as THREE.Mesh).geometry as THREE.BufferGeometry | undefined
      if (o.visible && g instanceof THREE.PlaneGeometry && g.parameters.width === 1 && g.parameters.height === 1) lit++
    })
    expect(lit).toBe(0)
  })

  it('is placed and scaled where it is told', () => {
    const kb = createHoloKeyboard(0xa855f7)
    kb.place(new THREE.Vector3(0.1, 1.2, 0.3), 0.4)
    expect(kb.group.position.toArray()).toEqual([0.1, 1.2, 0.3])
    expect(kb.group.scale.x).toBeCloseTo(0.4)
  })
})

describe('facing the typist', () => {
  /** World position of a key's centre, through the group's own transforms. */
  const keyWorld = (kb: ReturnType<typeof createHoloKeyboard>, row: number, col = 0) => {
    kb.group.updateMatrixWorld(true)
    const board = kb.group.getObjectByName('holo-keyboard-board') as THREE.Object3D
    const k = keyLayout()[row][col]
    return board.localToWorld(new THREE.Vector3(k.x, 0, k.z))
  }

  it('puts the space bar nearest the character and the number row nearest the camera', () => {
    const kb = createHoloKeyboard(0xa855f7)
    const rows = keyLayout()
    // The camera is at +z looking toward -z, the character behind the board.
    const numberRow = keyWorld(kb, 0)
    const spaceRow = keyWorld(kb, rows.length - 1)
    expect(spaceRow.z).toBeLessThan(numberRow.z)
  })

  it('mirrors left and right, as a board across the desk does', () => {
    const kb = createHoloKeyboard(0xa855f7)
    // Row 3 opens with a wide shift key on its left as drawn; seen from the
    // camera it must now be on the right.
    const first = keyWorld(kb, 3, 0)
    const last = keyWorld(kb, 3, keyLayout()[3].length - 1)
    expect(first.x).toBeGreaterThan(last.x)
  })

  it('keeps the tilt, so the key faces are still turned toward the camera', () => {
    const kb = createHoloKeyboard(0xa855f7)
    const rows = keyLayout()
    const nearCamera = keyWorld(kb, 0)
    const nearCharacter = keyWorld(kb, rows.length - 1)
    // The edge nearest the character is the raised one.
    expect(nearCharacter.y).toBeGreaterThan(nearCamera.y)
  })
})

describe('nothing beside the board', () => {
  it('draws no mouse: everything it shows is the board, inside its own width', () => {
    const kb = createHoloKeyboard(0xa855f7, () => 0.9)
    step(kb, 1, true)
    kb.group.updateMatrixWorld(true)
    const names: string[] = []
    kb.group.traverse((o) => names.push(o.name))
    expect(names.some((n) => /mouse/i.test(n))).toBe(false)
    expect('mouse' in kb).toBe(false)
    const box = new THREE.Box3().setFromObject(kb.group)
    // The scan line is the widest thing on it, at 1.06 of the board.
    expect(box.max.x).toBeLessThanOrEqual(0.54)
    expect(box.min.x).toBeGreaterThanOrEqual(-0.54)
  })
})

describe('where the board sits', () => {
  const hands = (lx: number, rx: number, y = 1.18, z = 0.26) => ({
    left: { x: lx, y, z },
    right: { x: rx, y, z },
  })

  it('takes its size and horizontal centre from the body, not the hands', () => {
    const a = boardPlacement({ ...hands(0.22, -0.1), centreX: 0.02, width: 0.8 }, null)
    const b = boardPlacement({ ...hands(0.3, -0.4), centreX: 0.02, width: 0.8 }, a)
    expect(a.width).toBe(0.8)
    expect(a.x).toBe(0.02)
    expect(b.width).toBe(0.8)
    expect(b.x).toBe(0.02)
  })

  it('holds height and depth while a hand has reached away', () => {
    const typing = boardPlacement({ ...hands(0.22, -0.1), centreX: 0, width: 0.8 }, null)
    const away = boardPlacement(
      { left: { x: 0.22, y: 1.18, z: 0.26 }, right: { x: -0.3, y: 1.4, z: 0.6 }, centreX: 0, width: 0.8 },
      typing,
    )
    expect(away).toEqual(typing)
  })

  it('moving one hand away changes neither size nor x, whatever the distance', () => {
    const typing = boardPlacement({ ...hands(0.22, -0.1), centreX: 0, width: 0.8 }, null)
    for (const rx of [-0.15, -0.3, -0.6, -2]) {
      const p = boardPlacement({ ...hands(0.22, rx), centreX: 0, width: 0.8 }, typing)
      expect(p.width).toBe(typing.width)
      expect(p.x).toBe(typing.x)
    }
  })

  it('follows the hands in height and depth while both are on the board', () => {
    const first = boardPlacement({ ...hands(0.22, -0.1, 1.18, 0.26), centreX: 0, width: 0.8 }, null)
    const lower = boardPlacement({ ...hands(0.22, -0.1, 1.0, 0.3), centreX: 0, width: 0.8 }, first)
    expect(lower.y).toBeLessThan(first.y)
    expect(lower.z).toBeGreaterThan(first.z)
  })

  it('eases toward a new reading rather than jumping', () => {
    const first = boardPlacement({ ...hands(0.22, -0.1, 1.18, 0.26), centreX: 0, width: 0.8 }, null)
    const target = boardPlacement({ ...hands(0.22, -0.1, 1.0, 0.26), centreX: 0, width: 0.8 }, first, 1)
    const eased = boardPlacement({ ...hands(0.22, -0.1, 1.0, 0.26), centreX: 0, width: 0.8 }, first, 0.25)
    expect(eased.y).toBeLessThan(first.y)
    expect(eased.y).toBeGreaterThan(target.y)
  })

  it('treats hands typing as on the board and a hand reaching out as off it', () => {
    // The shipped character, measured 12 October 2026: 0.30-0.35 apart typing
    // and 0.50-0.67 reaching out to its right, board 0.80 wide.
    expect(0.35).toBeLessThan(0.8 * HANDS_ON_BOARD)
    expect(0.5).toBeGreaterThan(0.8 * HANDS_ON_BOARD)
  })

  it('uses the hands when there is nothing to hold, so a board is shown somewhere', () => {
    const p = boardPlacement({ ...hands(0.22, -2), centreX: 0, width: 0.8 }, null)
    expect(p.y).toBeLessThan(1.18)
  })
})
