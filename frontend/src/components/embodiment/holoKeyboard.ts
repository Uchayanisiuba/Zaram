/**
 * A neon keyboard that appears under the character's hands while it codes.
 *
 * **Drawn here, not downloaded.** A modelled keyboard would be a second asset
 * to licence, ship and keep in style with a character it was not made for, and
 * `CLAUDE.md` holds that an avatar references nothing outside itself. Lines and
 * faint panes in the state's own colour weigh nothing, match any VRM a person
 * brings, and read as part of the state rather than a prop.
 *
 * **It belongs to a state, so it only ever reports one.** It is shown while
 * the state is `coding` and at no other time, in `STATE_PULSE.coding`'s colour,
 * so it cannot say something the rim and the glow do not.
 *
 * Appearing: a scan line sweeps across the board, the frame flickers on, and
 * the key rows come in one after another; while it stays, it shimmers and a few
 * keys light under the fingers. Leaving is the same, faster and in reverse.
 * With reduced motion it fades, with no flicker and no lit keys.
 *
 * **It faces the typist, and it stays where it was put.** The space bar is the
 * edge nearest the character and the number row the edge nearest the camera,
 * the way a real board sits in front of someone facing you; the surface is
 * still tilted toward the camera so the key faces read. And it is sized and
 * centred from the body (`boardPlacement`), never from where the hands happen
 * to be: the clip sends the right hand out to the character's right near its
 * end, and a board that followed the hands stretched toward it. Instead the
 * board is wide enough that the hand is still over it when it reaches -- a
 * mouse was drawn there for that moment, and was taken out (12 October 2026,
 * the maintainer's call) in favour of the board simply reaching that far.
 *
 * **Normal blending, never additive** -- the reason the glow behind the
 * character gives: the canvas is transparent and composited by the page, and
 * additive colour builds no alpha, so it would be present and invisible.
 */
import * as THREE from 'three'

/** Board proportions in its own units: 1 wide, `DEPTH` deep, lying flat. */
const DEPTH = 0.34
/** Key widths per row, in key units. A real layout's rhythm, not a real layout. */
const ROWS: number[][] = [
  [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
  [1.5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.5],
  [1.75, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.25],
  [2.25, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.75],
  [1.5, 1.25, 1.5, 6, 1.5, 1.25, 1.5],
]
const ROW_UNITS = 15
const GAP = 0.12 // of a key unit
const SPAWN_SECONDS = 0.7
const LEAVE_SECONDS = 0.35
/** How far the far edge is raised, so a camera at head height sees the face of it. */
export const TILT = 0.55

export interface Vec3 {
  x: number
  y: number
  z: number
}

export interface BoardPlacement {
  x: number
  y: number
  z: number
  /** Board width in world units. The board's depth follows from it. */
  width: number
}

/** How far apart the hands may be, as a share of the board's width, and still
 *  be taken as both resting on it. Measured 12 October 2026 on the shipped
 *  character, board 0.80 wide: typing keeps the hands 0.30-0.35 apart (under
 *  0.45 of the width) and the reach to the right takes them 0.50-0.67 apart
 *  (over 0.62). The line sits between, so the board holds still through the
 *  reach. */
export const HANDS_ON_BOARD = 0.55

/**
 * Where the board goes. Pure, so the one property that matters is testable:
 * **size and horizontal centre come from the body and never from the hands.**
 * Height and depth come from the hands, but only while both are on the board;
 * when one has reached away from it the last good placement is held, so the
 * board does not visibly move or resize through the clip.
 *
 * `smoothing` (0..1) is how far to move toward a fresh reading each call, so
 * the board sits still while the fingers tap. With no previous placement the
 * hands are used as they are, because a board somewhere is better than none.
 */
export function boardPlacement(
  input: { left: Vec3; right: Vec3; centreX: number; width: number },
  previous: BoardPlacement | null,
  smoothing = 1,
): BoardPlacement {
  const { left, right, centreX, width } = input
  const apart = Math.hypot(left.x - right.x, left.y - right.y, left.z - right.z)
  const onBoard = apart <= width * HANDS_ON_BOARD
  if (previous && !onBoard) return { x: centreX, y: previous.y, z: previous.z, width }
  const y = Math.min(left.y, right.y) - width * 0.09
  const z = (left.z + right.z) / 2 + width * 0.1
  if (!previous) return { x: centreX, y, z, width }
  return {
    x: centreX,
    y: previous.y + (y - previous.y) * smoothing,
    z: previous.z + (z - previous.z) * smoothing,
    width,
  }
}

export interface KeyRect {
  x: number
  z: number
  w: number
  d: number
}

/** Every key's rectangle in board units, row by row. Exported for the test. */
export function keyLayout(): KeyRect[][] {
  const unit = 0.94 / ROW_UNITS
  const rowDepth = (DEPTH * 0.86) / ROWS.length
  return ROWS.map((row, r) => {
    const total = row.reduce((a, b) => a + b, 0)
    let x = -(total * unit) / 2
    const z = -DEPTH * 0.43 + rowDepth * (r + 0.5)
    return row.map((w) => {
      const rect = { x: x + (w * unit) / 2, z, w: (w - GAP) * unit, d: rowDepth * (1 - GAP * 1.4) }
      x += w * unit
      return rect
    })
  })
}

function outline(rects: KeyRect[], y: number): THREE.BufferGeometry {
  const p: number[] = []
  for (const k of rects) {
    const x0 = k.x - k.w / 2
    const x1 = k.x + k.w / 2
    const z0 = k.z - k.d / 2
    const z1 = k.z + k.d / 2
    p.push(x0, y, z0, x1, y, z0, x1, y, z0, x1, y, z1, x1, y, z1, x0, y, z1, x0, y, z1, x0, y, z0)
  }
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.Float32BufferAttribute(p, 3))
  return g
}

function panes(rects: KeyRect[], y: number): THREE.BufferGeometry {
  const p: number[] = []
  for (const k of rects) {
    const x0 = k.x - k.w / 2
    const x1 = k.x + k.w / 2
    const z0 = k.z - k.d / 2
    const z1 = k.z + k.d / 2
    p.push(x0, y, z0, x0, y, z1, x1, y, z1, x0, y, z0, x1, y, z1, x1, y, z0)
  }
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.Float32BufferAttribute(p, 3))
  return g
}

function roundedFrame(w: number, d: number, r: number): THREE.BufferGeometry {
  const pts: THREE.Vector3[] = []
  const corners: [number, number, number][] = [
    [w / 2 - r, -d / 2 + r, -Math.PI / 2],
    [w / 2 - r, d / 2 - r, 0],
    [-w / 2 + r, d / 2 - r, Math.PI / 2],
    [-w / 2 + r, -d / 2 + r, Math.PI],
  ]
  for (const [cx, cz, start] of corners) {
    for (let i = 0; i <= 6; i++) {
      const a = start + (i / 6) * (Math.PI / 2)
      pts.push(new THREE.Vector3(cx + Math.cos(a) * r, 0, cz + Math.sin(a) * r))
    }
  }
  pts.push(pts[0].clone())
  return new THREE.BufferGeometry().setFromPoints(pts)
}

const lineMat = (colour: THREE.Color) =>
  new THREE.LineBasicMaterial({ color: colour, transparent: true, opacity: 0, depthWrite: false, toneMapped: false })
const paneMat = (colour: THREE.Color) =>
  new THREE.MeshBasicMaterial({
    color: colour,
    transparent: true,
    opacity: 0,
    depthWrite: false,
    toneMapped: false,
    side: THREE.DoubleSide,
  })

const ease = (t: number) => 1 - Math.pow(1 - Math.min(Math.max(t, 0), 1), 3)
const clamp01 = (t: number) => Math.min(Math.max(t, 0), 1)

export interface HoloKeyboard {
  group: THREE.Group
  /** 0 when gone, 1 when fully shown. Exported for the test and the debug hook. */
  readonly shown: number
  /** Advance the appearance by `dt` seconds toward shown (`active`) or gone. */
  update(dt: number, now: number, active: boolean, reducedMotion: boolean): void
  /** Centre the board at `centre` (world), `width` across. */
  place(centre: THREE.Vector3, width: number): void
  dispose(): void
}

export function createHoloKeyboard(colourHex: number, random: () => number = Math.random): HoloKeyboard {
  const base = new THREE.Color(colourHex)
  // Lines a little toward white so they read as lit edges against their own panes.
  const bright = base.clone().lerp(new THREE.Color(0xffffff), 0.5)

  const group = new THREE.Group()
  group.name = 'holo-keyboard'
  group.visible = false
  group.renderOrder = 10
  // The tilted surface the board lies in.
  const tilt = new THREE.Group()
  tilt.rotation.x = TILT
  group.add(tilt)
  // The keys are drawn with the number row at -z. Turned half a turn about the
  // vertical, inside the tilt, the rows reverse and left and right mirror --
  // what a board looks like from across the desk -- while the tilt toward the
  // camera is kept. Space bar nearest the character, number row nearest us.
  const board = new THREE.Group()
  board.name = 'holo-keyboard-board'
  board.rotation.y = Math.PI
  tilt.add(board)

  const frameMat = lineMat(bright)
  const frame = new THREE.LineLoop(roundedFrame(1, DEPTH, 0.03), frameMat)
  const deckMat = paneMat(base)
  const deck = new THREE.Mesh(new THREE.PlaneGeometry(1, DEPTH).rotateX(-Math.PI / 2), deckMat)
  board.add(deck, frame)

  const layout = keyLayout()
  const rows = layout.map((rects) => {
    const lines = new THREE.LineSegments(outline(rects, 0.004), lineMat(bright))
    const fill = new THREE.Mesh(panes(rects, 0.003), paneMat(base))
    board.add(fill, lines)
    return { lines, fill }
  })

  const scanMat = paneMat(bright)
  const scan = new THREE.Mesh(new THREE.PlaneGeometry(1.06, DEPTH * 0.05).rotateX(-Math.PI / 2), scanMat)
  scan.position.y = 0.006
  board.add(scan)

  // A few keys lit under the fingers. A small pool rather than one per key.
  const allKeys = layout.flat()
  const flashes = Array.from({ length: 5 }, () => {
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), paneMat(bright))
    mesh.position.y = 0.005
    board.add(mesh)
    return { mesh, life: 0 }
  })
  let nextFlash = 0

  let shown = 0
  let wasActive = false

  const keyboard: HoloKeyboard = {
    group,
    get shown() {
      return shown
    },
    update(dt, now, active, reducedMotion) {
      const step = dt / (active ? SPAWN_SECONDS : LEAVE_SECONDS)
      shown = clamp01(shown + (active ? step : -step))
      if (active !== wasActive) wasActive = active
      group.visible = shown > 0
      if (!group.visible) return

      const p = ease(shown)
      const settled = shown >= 1
      // A hologram powering up does not ramp smoothly: it catches, drops and
      // catches. Only while it is arriving or leaving, and never for reduced motion.
      const flicker = settled || reducedMotion ? 1 : random() > 0.22 ? 1 : 0.25
      const shimmer = reducedMotion ? 1 : 0.88 + 0.12 * Math.sin(now * 3.1)

      board.scale.set(reducedMotion ? 1 : 0.7 + 0.3 * p, 1, 1)
      frameMat.opacity = p * flicker * shimmer
      deckMat.opacity = 0.12 * p * shimmer
      rows.forEach((row, i) => {
        const r = reducedMotion ? p : ease((shown * 1.6 - 0.25 - i * 0.12) / 0.45)
        row.lines.material.opacity = r * flicker * shimmer
        row.fill.material.opacity = 0.22 * r * shimmer
      })

      // The scan line crosses the board once on the way in and once on the way out.
      scan.visible = !reducedMotion && !settled
      // From the near-camera edge to the far one, as it always did; the board is
      // turned, so that is the other way round in its own coordinates.
      scan.position.z = THREE.MathUtils.lerp(-DEPTH / 2, DEPTH / 2, shown)
      scanMat.opacity = 0.9 * Math.sin(Math.PI * shown)

      for (const f of flashes) {
        f.life = Math.max(0, f.life - dt * 3.5)
        f.mesh.visible = f.life > 0
        f.mesh.material.opacity = 0.75 * f.life * p
      }
      if (settled && active && !reducedMotion && now >= nextFlash) {
        nextFlash = now + 0.07 + random() * 0.12
        const slot = flashes.find((f) => f.life === 0)
        if (slot) {
          const k = allKeys[Math.floor(random() * allKeys.length)]
          slot.mesh.position.x = k.x
          slot.mesh.position.z = k.z
          slot.mesh.scale.set(k.w, 1, k.d)
          slot.life = 1
        }
      }
    },
    place(centre, width) {
      group.position.copy(centre)
      group.scale.setScalar(width)
    },
    dispose() {
      group.traverse((o) => {
        const m = o as THREE.Mesh
        m.geometry?.dispose()
        const mat = m.material as THREE.Material | THREE.Material[] | undefined
        for (const one of Array.isArray(mat) ? mat : mat ? [mat] : []) one.dispose()
      })
    },
  }
  return keyboard
}
