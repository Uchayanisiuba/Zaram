import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { Brain, BookOpen, FileText, Layers, Settings, ShieldCheck } from 'lucide-react'
import { ORB_BEHAVIOUR } from '../components/orb/LivingOrb'
import Embodiment from '@/components/embodiment/Embodiment'
import OrbStatusLabel from '../components/orb/OrbStatusLabel'
import OrbHint from '../components/orb/OrbHint'
import OrbAura from '../components/orb/OrbAura'
import { useEmbodimentStore } from '@/stores/embodimentStore'
import { useChatModeStore } from '@/stores/chatModeStore'
import { useLayoutStore, orbGeometry } from '@/stores/layoutStore'
import { useSourceStore } from '@/stores/sourceStore'
import { useIsReducedMotion } from '@/hooks/useReducedMotion'
import { useViewport } from '@/hooks/useViewport'

import type { WorkspaceId } from '@/runtime/shortcuts/registry'

// Build, Canvas and Plugins are out of scope for v1 and no longer appear here.
// Their surfaces are preserved in src/legacy/.
//
// Six nodes, each answering a different question the user actually has:
// Work — what have I got out of this? Project — how is it grouped?
// Memory — what do you know about me? Knowledge — what have you read?
// Activity — what did you send? Settings — how do you behave?
//
// Re-spaced 120 → 90 → 72 → 60 degrees as Activity, Work and then Project
// joined. Six is the count; a seventh needs a reason that survives "why is this
// not part of Conversation?".
//
// Work is first because it is the only node holding something the user made,
// and Project sits beside it because they are adjacent and distinct: Work is
// the output, Project is the organisation of it. Project earned a node rather
// than being a filter inside Work because `project:<id>` scopes *facts* — it
// reaches the Spine, and a filter inside Work cannot own something that scopes
// Memory. See CLAUDE.md, 10 August 2026.
//
// Two icons are deliberately the odd ones out. Activity's shield is evidence
// rather than exploration — someone arriving there is checking, not browsing.
// Work's document is an artifact rather than a view of one. Project's layers
// are grouping and deliberately **not** a folder, which would promise the tree
// the product refuses to build.
//
// **The order and membership are checked against `orbitOrder`** below. This
// list was a restatement of the canonical one and drifted from it the moment
// Project was added to the registry: the node existed in the rail, in the command palette and in
// the router, and the orbit — the first thing anyone sees — silently kept
// showing five. `orbitOrder` had no consumers at all, which is how a "canonical
// list" stays canonical only in its docstring.
const ORBIT_START_ANGLE = 198
const ORBIT_STEP = 60

export const ORBITAL_NODES = [
  { id: 'work',      label: 'Work',      icon: <FileText size={24} />,    color: '#e5a44c' },
  { id: 'project',   label: 'Project',   icon: <Layers size={24} />,      color: '#f472b6' },
  { id: 'memory',    label: 'Memory',    icon: <Brain size={24} />,       color: '#c084fc' },
  { id: 'knowledge', label: 'Knowledge', icon: <BookOpen size={24} />,    color: '#22d3ee' },
  { id: 'activity',  label: 'Activity',  icon: <ShieldCheck size={24} />, color: '#34d399' },
  { id: 'settings',  label: 'Settings',  icon: <Settings size={24} />,    color: '#94a3b8' },
].map((node, i) => ({
  // Derived rather than written out, so the spacing cannot drift out of step
  // with the count the next time a node is added or removed.
  ...node,
  angle: (ORBIT_START_ANGLE + i * ORBIT_STEP) % 360,
}))

interface LandingProps {
  onNavigate: (id: WorkspaceId) => void
  onOrbTap?: () => void
}

const ORB_SIZE = 320
const ORBIT_RADIUS = 240
/** The orbital system is rendered inside this scale, so any transform applied
 *  within it is multiplied by the same factor. See orbGeometry(). */
const CONTAINER_SCALE = 1.4

export default function Landing({ onNavigate, onOrbTap }: LandingProps) {
  const [_, setHovered] = useState<string | null>(null)
  const reduced = useIsReducedMotion()

  /** Which node is being dragged, or null. State rather than a ref because the
   *  render reads it: the held node is lifted above its siblings, and its drift
   *  compensation is computed from it. */
  const [dragging, setDragging] = useState<string | null>(null)
  /** The orbit angle at the moment the drag began.
   *
   *  **The orbit does not stop for a drag.** The other five nodes keep going
   *  round, so the held one has to be pinned against a moving frame: its slot
   *  advances underneath it, and the compensation below cancels that so the
   *  node stays under the pointer. Releasing removes the compensation, which
   *  returns the node to the slot it *would* have reached had it never been
   *  picked up — its place relative to the others, not the place it left.
   *
   *  A ref, not state: `orbitAngle` already re-renders every frame, so this is
   *  read fresh without scheduling a second render per frame. */
  const dragFromAngle = useRef(0)
  /** Set on drag start, cleared a tick after drag end. A drag ends with a
   *  pointerup over the button, which the browser then reports as a click — so
   *  without this, letting go of Memory navigates to Memory. */
  const draggedRef = useRef(false)
  const { chatView, closeChat } = useChatModeStore()
  const chat = chatView === 'chat'

  // The orb's position and size are derived from the conversation panel's
  // width, so dragging the panel moves the orb with it.
  const chatFraction = useLayoutStore((s) => s.chatFraction)
  const isResizing = useLayoutStore((s) => s.isResizing)
  // Source panels open in the orb's space. While any is open the orb recedes —
  // blurred and dimmed — so the panel reads as being in front of it rather than
  // competing with it. It returns when the last panel closes.
  const panelsOpen = useSourceStore((s) => s.open.length > 0)
  // Spike only. The shipped control belongs in Settings — see
  // docs/EMBODIMENT-SPIKE.md, "the toggle lives in Settings, the landing gets
  // nothing". It is here so the two renderers can be compared side by side,
  // which is the only way to answer whether the avatar is worth shipping.
  const renderer = useEmbodimentStore((s) => s.renderer)
  // The health poll used to start here, because the top bar is hidden on this
  // surface and nothing else was mounted to own it. The persistent bar is
  // mounted on every surface including this one, so it owns the poll now — two
  // callers would mean two intervals.
  const { width: viewportWidth, height: viewportHeight } = useViewport()

  /**
   * The scale the orbital system **fits in**, not the one it was designed at.
   *
   * `CONTAINER_SCALE` is 1.4 and was applied unconditionally — and a second,
   * hardcoded `scale(1.4)` sat on the wrapper below, which is the "two
   * formulae for one position" that `LandingHint` warns about in its own
   * docstring. At 1.4 the outer ring is 826px across, so on any window under
   * about 1030px tall it does not fit, and the caption slot below it has
   * nowhere to go.
   *
   * The comment on `captionTop` records the previous attempt: it moved the
   * *caption* down as far as it would go and concluded that "on a 900px window
   * the ring alone is 826px and there is genuinely nowhere below it". That is
   * true, and it is the wrong thing to accept — the caption was made to yield
   * to a ring that had no business being that size on that screen. Measured 10
   * September on an 800px window: ring 826px, footer 52px, overlap 52px, the
   * hint sitting on the Settings and Activity labels.
   *
   * So the ring yields instead. Solve for the scale at which the ring's lower
   * edge, its margin and the caption block all land inside the window:
   *
   *     vh/2 + (D·scale)/2 + GAP + CAPTION <= vh
   *     scale <= (vh - 2·GAP - 2·CAPTION) / D
   *
   * capped at the design scale so a large monitor still gets exactly what was
   * drawn, and floored so a very small window shrinks rather than collapsing.
   * Width is checked too — a wide-but-short window and a narrow-but-tall one
   * fail differently and both fail.
   */
  /**
   * Reserved above and below, and they are **not the same number** -- which is
   * the whole reason the first version of this shrank too far.
   *
   * A centred ring pays twice for every pixel reserved, so a symmetric reserve
   * spends the top margin on a caption that only exists at the bottom. The
   * first fix reserved 104px each side and took the ring from 826px to 592px
   * on an 800px window: correct, and much smaller than it needed to be.
   *
   * Measured on the running app, 10 September: the caption line is **24px**
   * tall with 14px beneath it. `BOTTOM` allows two of those lines, because the
   * slot carries the locality label -- "Local only", "Local . can send",
   * "Cloud enabled" -- as well as the hint, and a reserve that fits one line
   * collides the moment the second appears. `TOP` is margin only; nothing
   * lives up there but the mark in the corner.
   */
  const TOP_RESERVE = 20
  const BOTTOM_RESERVE = 96
  const RING_GAP = 28
  const CAPTION_BLOCK = 76
  const DESIGN_DIAMETER = ORBIT_RADIUS * 2 + 110

  /**
   * The scale the orbital system **fits in**, not the one it was designed at.
   *
   * `CONTAINER_SCALE` is 1.4 and was applied unconditionally -- and a second,
   * hardcoded `scale(1.4)` sat on the wrapper below, the "two formulae for one
   * position" that `LandingHint` warns about in its own docstring. At 1.4 the
   * outer ring is 826px across, so on any window under about 1030px tall it
   * does not fit and the caption below it has nowhere to go.
   *
   * `captionTop`'s comment records the previous attempt: it moved the *caption*
   * down as far as it would go and concluded that "on a 900px window the ring
   * alone is 826px and there is genuinely nowhere below it". True, and the
   * wrong thing to accept -- the caption was made to yield to a ring that had
   * no business being that size on that screen. Now the ring yields, and
   * because the reserve is asymmetric it barely has to: 794px at 910px tall
   * against the 826px it was drawn at.
   */
  const availableHeight = viewportHeight - TOP_RESERVE - BOTTOM_RESERVE
  const fitScale = Math.max(
    0.62,
    Math.min(CONTAINER_SCALE, availableHeight / DESIGN_DIAMETER, viewportWidth / DESIGN_DIAMETER),
  )

  /**
   * Centred in the band it was given, not in the window.
   *
   * A constant `(TOP_RESERVE - BOTTOM_RESERVE) / 2`, which is the only honest
   * consequence of reserving different amounts at each end. Without it the ring
   * would be sized for the band and then drawn in the middle of the window,
   * which puts back the collision at the bottom and wastes the room at the top.
   */
  const orbitOffsetY = (TOP_RESERVE - BOTTOM_RESERVE) / 2

  const { shiftX, zoom } = orbGeometry({
    viewportWidth,
    chatFraction,
    chatOpen: chat,
    orbSize: ORB_SIZE,
    containerScale: fitScale,
  })

  // --- Orbital rAF: gated to 'landing' so the orbit FREEZES during chat.
  // Continuity refs ensure the loop resumes from the frozen angle (no jump to 0).
  const [orbitAngle, setOrbitAngle] = useState(0)
  const rafRef = useRef<number>(0)
  const startRef = useRef<number>(0)
  const offsetRef = useRef<number>(0)
  const elapsedRef = useRef<number>(0)

  useEffect(() => {
    if (chat) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      return
    }
    // On resume, continue from the frozen elapsed time so the angle is continuous.
    if (elapsedRef.current > 0) {
      offsetRef.current = elapsedRef.current
      startRef.current = 0
    }
    const tick = (ts: number) => {
      if (!startRef.current) startRef.current = ts
      const elapsed = (ts - startRef.current) + offsetRef.current
      elapsedRef.current = elapsed
      setOrbitAngle((elapsed / 90000) * 360)
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [chat])

  // Escape reverses the transition (closes chat).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && chat) closeChat()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [chat, closeChat])

  const ring1Size = ORBIT_RADIUS * 2 + 60
  const ring2Size = ORBIT_RADIUS * 2 + 110

  /**
   * Where the low caption slot sits — the status label and the first-run hint.
   *
   * **It was `bottom: 8%`, and a percentage of the window cannot clear a ring
   * measured in pixels.** The outer ring is centred on the orb and renders at
   * `ring2Size * CONTAINER_SCALE` — 826px across — while the caption was
   * anchored to the bottom edge, so the gap between them was whatever the
   * window height happened to leave. On a laptop it left none: the text landed
   * inside the ring's lower arc, which is what the maintainer photographed.
   *
   * Anchored to the thing it has to stay clear of instead. Below the ring's
   * bottom edge with a real margin whenever the window is tall enough, and as
   * low as it will go otherwise — because on a 900px window the ring alone is
   * 826px and there is genuinely nowhere below it. Saying so in the arithmetic
   * beats a percentage that is right on one monitor.
   */
  const ringBottomFromCentre = (ring2Size / 2) * fitScale
  const captionTop = Math.min(
    viewportHeight / 2 + orbitOffsetY + ringBottomFromCentre + RING_GAP,
    // Never off the bottom. Two lines of note plus its own breathing room.
    viewportHeight - CAPTION_BLOCK,
  )

  const orbShift = { scale: zoom, x: shiftX, y: 0 }
  // orbGeometry divides by the container scale for use *inside* the scaled
  // wrapper. Anything outside it needs the undivided value.
  const visualShiftX = shiftX * fitScale
  const orbTransition = isResizing
    ? // Track the divider exactly while it is being dragged; a spring here
      // makes the orb drift behind the panel edge.
      { duration: 0 }
    : chat
      ? reduced ? { type: 'tween' as const, duration: 0.22 } : { type: 'spring' as const, stiffness: 200, damping: 24 }
      : { type: 'tween' as const, duration: 0.35 }

  return (
    <div
      className="h-screen overflow-hidden text-slate-100 flex items-center justify-center w-full flex-1"
      // Gradient and grid now come from .zaram-backdrop on the app shell, so
      // the landing and the workspaces share one ground instead of the landing
      // painting its own.
      style={{ fontFamily: 'var(--font-display), var(--font-sans), sans-serif' }}
    >
      {/* The mark, in the corner it occupies on every other surface.

          `ZaramMark` argues it should be absent here — the landing is already
          the brand moment and a second mark competes with the orb — and that
          argument is what shapes this rather than what excludes it. So it is
          answered instead of overridden: small, dimmed, and outside the scaled
          orbital container, which puts it far enough from the orb that the two
          are never read together.

          Not `ZaramMark` itself, and not a button. That component's job is the
          route home, and on the landing you are home — a control that looks
          live and does nothing is the lie TopNav's own comments argue against.
          This is the same silhouette doing a different job: telling you which
          application you are looking at while nothing else on screen does.

          It also gives the landing somewhere to put the locality line, which
          at rest currently reports nowhere. */}
      <div
        className="absolute left-8 top-7 z-20 pointer-events-none select-none"
        style={{ opacity: panelsOpen ? 0.25 : 0.55, transition: 'opacity 0.35s ease' }}
        aria-hidden
        data-testid="landing-mark"
      >
        {/* The mark sits on a tile, 10 September.
         *
         * Same surface language as the six nav chips — `rounded-2xl`, glass,
         * `blur(10px)`, the same drop shadow — because a second visual idiom
         * on a surface this sparse reads as an accident. **Quieter than they
         * are, deliberately**: no coloured glow and no hover, because this is
         * identity rather than a target and it is already `pointer-events-none`
         * and `aria-hidden`. A tile that looked exactly like a nav chip would
         * invite a click that goes nowhere.
         *
         * Indigo, and the choice is not aesthetic. `docs/UI-SPEC.md` assigns
         * violet to **cloud**, so a violet tile would put "your data left the
         * device" in the corner of a resting screen — the 15 August face-colour
         * argument in `CLAUDE.md`, which lands on indigo for the same reason:
         * it is the implementation's own accent and it is nobody's state.
         *
         * The gradient runs from the accent to nothing rather than between two
         * colours. Two stops of equal weight make a badge; one fading out
         * makes a surface catching light. */}
        <div
          className="w-[60px] h-[60px] rounded-2xl flex items-center justify-center"
          style={{
            background:
              'linear-gradient(145deg, rgba(99,102,241,0.20), rgba(255,255,255,0.03))',
            border: '1px solid rgba(99,102,241,0.28)',
            backdropFilter: 'blur(10px)',
            boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
          }}
        >
        <img
          src="/brand/zaram-mark.svg"
          alt=""
          // Doubled from 28 on 10 September. At 28 the mark was legible only
          // as a smudge in the corner — it is the one thing on this surface
          // saying which application you are looking at, and the landing is
          // otherwise wordless. The opacity above still keeps it quiet.
          width={38}
          height={38}
          // The asset may not exist yet — see `public/brand/README.md`. A
          // broken image icon in the corner of the landing would be worse than
          // no mark at all, so a failure removes it rather than showing the
          // browser's placeholder.
          onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
        />
        </div>
      </div>

      {/* Orbital system — keeps the same shell; only the orbital motion is gated. */}
      <div
        className="relative w-full h-full flex items-center justify-center"
        // One value, computed above. The literal that used to sit here
        // disagreed with `CONTAINER_SCALE` the moment either changed.
        style={{
          transform: `translateY(${orbitOffsetY}px) scale(${fitScale})`,
          transformOrigin: 'center center',
        }}
      >
        {/* Orbit track rings — dissolve / restore (centering via framer offset, never inline transform). */}
        <motion.div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: ring1Size, height: ring1Size,
            left: '50%', top: '50%',
            x: -(ring1Size / 2), y: -(ring1Size / 2),
            border: '1px solid rgba(255,255,255,0.04)',
          }}
          initial={false}
          animate={chat ? { opacity: 0, scale: reduced ? 1 : 1.15 } : { opacity: 1, scale: 1 }}
          transition={{ duration: reduced ? 0.2 : 0.4 }}
        />
        <motion.div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: ring2Size, height: ring2Size,
            left: '50%', top: '50%',
            x: -(ring2Size / 2), y: -(ring2Size / 2),
            border: '1px solid rgba(255,255,255,0.025)',
          }}
          initial={false}
          animate={chat ? { opacity: 0, scale: reduced ? 1 : 1.15 } : { opacity: 1, scale: 1 }}
          transition={{ duration: reduced ? 0.2 : 0.4, delay: 0.04 }}
        />

        {/* Central Living Orb — zooms + glides into the open space beside the chat. */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 flex flex-col items-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{
              opacity: panelsOpen ? 0.35 : 1,
              filter: panelsOpen ? 'blur(8px)' : 'blur(0px)',
              ...orbShift,
              scale: orbShift.scale * (panelsOpen ? 0.96 : 1),
            }}
            transition={chat || isResizing ? orbTransition : { duration: 0.4 }}
            whileTap={{ scale: zoom * 0.9 }}
            data-testid="orb-tap"
            role="button"
            tabIndex={panelsOpen ? -1 : 0}
            aria-label="Talk to Zaram"
            style={{ cursor: panelsOpen ? 'default' : 'pointer' }}
            onClick={panelsOpen ? undefined : onOrbTap}
            onKeyDown={(e) => {
              // The orb was a clickable div, so it could not be reached or
              // activated from the keyboard at all.
              if (panelsOpen) return
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onOrbTap?.()
              }
            }}
          >
            <div style={{ width: ORB_SIZE, height: ORB_SIZE, position: 'relative' }}>
              {/* The aura, for the avatar.
               *
               * **The orb draws its own rings and motes; the character drew
               * neither**, so choosing it removed the state-coloured rings,
               * the particle field and the atmosphere with them — a robot on a
               * flat background. `OrbAura` is the same two rings and the same
               * ten motes, extracted so there is one state→colour table.
               *
               * Inside this box rather than beside it, which is why it
               * survives into the conversation: this is the element carrying
               * `orbShift` and the zoom, so the aura travels and scales with
               * the character exactly as the orb's own does. A sibling pinned
               * to the container's centre stayed behind when the character
               * glided left, which is what the first attempt did.
               *
               * Only on the avatar path — the orb draws its own inside itself,
               * and rendering both would double every ring and every mote.
               */}
              {renderer === 'avatar' && (
                <OrbAura px={ORB_SIZE} dimmed={panelsOpen} />
              )}

              {/* Above the aura, always. The avatar is a WebGL canvas in
                  normal flow, so without a stacking context of its own a
                  particle could paint across the face — and a mote crossing
                  the visor reads as something the face is doing. */}
              <div style={{ position: 'relative', zIndex: 1 }}>
              <Embodiment key={renderer} px={ORB_SIZE} {...ORB_BEHAVIOUR} />
              </div>
            </div>
          </motion.div>

        </div>

        {/* Orbiting satellite nodes — parent holds the FROZEN orbit (rAF), child
            carries the dispersal via framer so the two transforms never fight. */}
        {ORBITAL_NODES.map((node) => {
          const animatedRad = ((node.angle - 90 + orbitAngle) * Math.PI) / 180
          const restX = Math.cos(animatedRad) * ORBIT_RADIUS
          const restY = Math.sin(animatedRad) * ORBIT_RADIUS

          // Drift compensation, and only for the node in hand. Its slot keeps
          // advancing with the rest of the orbit, so without this the node
          // would creep out from under the pointer at ~17px/s. Holding it still
          // against a moving frame costs exactly the distance the slot has
          // travelled since the drag began.
          const heldRad = ((node.angle - 90 + dragFromAngle.current) * Math.PI) / 180
          const held = dragging === node.id
          const driftX = held ? Math.cos(heldRad) * ORBIT_RADIUS - restX : 0
          const driftY = held ? Math.sin(heldRad) * ORBIT_RADIUS - restY : 0
          // Dispersal target: push ~0.8 * ORBIT_RADIUS further along the same angle.
          const dx = Math.cos(animatedRad) * ORBIT_RADIUS * 0.8
          const dy = Math.sin(animatedRad) * ORBIT_RADIUS * 0.8

          const dispersed = chat
            ? reduced ? { opacity: 0 } : { opacity: 0, scale: 0.4, x: dx, y: dy }
            : reduced ? { opacity: 1 } : { opacity: 1, scale: 1, x: 0, y: 0 }
          // Leaving is snappier than returning. A dispersal that eases out feels
          // like lag on a click; arriving back can afford to settle.
          const childTransition = reduced
            ? { duration: 0.18 }
            : chat
              ? { type: 'spring' as const, stiffness: 420, damping: 30 }
              : { type: 'spring' as const, stiffness: 240, damping: 26 }

          return (
            <div
              key={node.id}
              className="absolute flex flex-col items-center gap-2"
              style={{
                left: '50%', top: '50%',
                transform: `translate(-50%, -50%) translate(${restX}px, ${restY}px)`,
                pointerEvents: chat ? 'none' : 'auto',
                // Lifted while held, so a node dragged across the ring passes
                // over its siblings instead of sliding beneath them.
                zIndex: dragging === node.id ? 40 : 20,
              }}
            >
              <motion.div
                initial={false}
                animate={dispersed}
                // No delay on the way out. The stagger was keyed to each node's
                // angle, so Knowledge at 330 degrees waited 0.33s before it
                // began moving — long enough after the click to read as lag.
                // A short stagger stays on the return, where settling back in
                // sequence looks deliberate rather than late.
                transition={{
                  ...childTransition,
                  delay: chat ? 0 : 0.03 * (node.angle / 90),
                }}
              >
                {/* Drag lives in its own layer, for the reason the comment
                    above gives about the orbit and the dispersal: three
                    concerns each own one transform, so none of them fights the
                    others. The parent holds the orbit position, the layer above
                    holds the dispersal, and this one holds the offset from the
                    pointer — which is why letting go can simply return this
                    layer to zero without knowing where the node belongs.

                    `dragSnapToOrigin` is the whole "returns to its revolution"
                    behaviour: origin here *is* the orbit slot, and it keeps
                    turning underneath while the spring plays out. */}
                {/* Drift compensation. Zero except for the node being held, and
                    animated to zero the instant it is let go — which is what
                    delivers it back to where it *would* have been rather than
                    to where it was picked up. Instant while held so it tracks
                    the orbit frame by frame; sprung on release so it arrives
                    with the same weight as the pointer offset beside it. */}
                <motion.div
                  animate={{ x: driftX, y: driftY }}
                  transition={
                    held
                      ? { duration: 0 }
                      : reduced
                        ? { type: 'tween', duration: 0.16 }
                        : { type: 'spring', stiffness: 320, damping: 26 }
                  }
                >
                <motion.div
                  drag={!chat}
                  dragSnapToOrigin
                  // No momentum. A flick that sends a menu item coasting across
                  // the screen is a toy; this is a nudge that springs back.
                  dragMomentum={false}
                  // Slightly under 1 so a long pull resists, which is what makes
                  // the return read as elastic rather than as a reset.
                  dragElastic={0.9}
                  whileDrag={{ scale: 1.06, cursor: 'grabbing' }}
                  dragTransition={{ bounceStiffness: 320, bounceDamping: 26 }}
                  transition={
                    reduced
                      ? { type: 'tween', duration: 0.16 }
                      : { type: 'spring', stiffness: 320, damping: 26 }
                  }
                  onDragStart={() => {
                    draggedRef.current = true
                    // Captured before the state update, so the first compensated
                    // frame measures from where the node actually was.
                    dragFromAngle.current = orbitAngle
                    setDragging(node.id)
                  }}
                  onDragEnd={() => {
                    setDragging(null)
                    // Cleared next tick, not immediately: the click this drag is
                    // about to produce has not been dispatched yet.
                    setTimeout(() => {
                      draggedRef.current = false
                    }, 0)
                  }}
                  style={{ cursor: 'grab', touchAction: 'none' }}
                >
                <motion.button
                  onClick={() => {
                    // A drag that ends over the node would otherwise navigate,
                    // so moving Memory out of the way and letting go would open
                    // Memory — the one outcome the gesture must not have.
                    if (draggedRef.current) return
                    onNavigate(node.id as WorkspaceId)
                  }}
                  onHoverStart={() => setHovered(node.id)}
                  onHoverEnd={() => setHovered(null)}
                  className="relative flex flex-col items-center"
                  whileHover={{ scale: 1.18 }}
                  whileTap={{ scale: 0.94 }}
                >
                  <motion.div
                    className="w-14 h-14 rounded-2xl flex items-center justify-center"
                    style={{
                      background: 'rgba(255,255,255,0.05)',
                      border: `1px solid ${node.color}35`,
                      backdropFilter: 'blur(10px)',
                      boxShadow: `0 4px 24px rgba(0,0,0,0.3)`,
                    }}
                    whileHover={{
                      background: `${node.color}18`,
                      borderColor: `${node.color}70`,
                      boxShadow: `0 0 24px ${node.color}50, 0 4px 24px rgba(0,0,0,0.3)`,
                    }}
                    transition={{ duration: 0.2 }}
                  >
                    {node.icon}
                  </motion.div>
                  <span
                    className="text-slate-400 whitespace-nowrap select-none"
                    style={{ fontSize: '11px', letterSpacing: '0.03em' }}
                  >
                    {node.label}
                  </span>
                </motion.button>
                </motion.div>
                </motion.div>
              </motion.div>
            </div>
          )
        })}
      </div>

      {/* Status, in words. Only while the conversation is open: at rest the
          landing is meant to be quiet, and there is nothing to report until you
          are about to ask something.

          Rendered outside the scale(1.4) orbital wrapper on purpose — inside it
          every offset is multiplied, which is what put the text within the ring
          radius. Anchored low instead, well clear of both rings. */}
      {chat && (
        <motion.div
          className="absolute left-1/2 z-20"
          style={{ bottom: '8%' }}
          initial={{ opacity: 0, y: 6 }}
          animate={{
            opacity: panelsOpen ? 0 : 1,
            y: 0,
            // Outside the scaled container the shift is the real pixel value,
            // not the pre-divided one the orb uses.
            x: `calc(-50% + ${visualShiftX}px)`,
          }}
          exit={{ opacity: 0 }}
          transition={isResizing ? { duration: 0 } : { duration: reduced ? 0.15 : 0.35, delay: reduced ? 0 : 0.1 }}
        >
          <OrbStatusLabel dimmed={panelsOpen} compact />
        </motion.div>
      )}

      {/* First-run instruction, in the same low slot. Shown only before the
          conversation has ever been opened, so it never competes with the
          status label above. */}
      <OrbHint offsetX={visualShiftX} top={captionTop} />

    </div>
  )
}
