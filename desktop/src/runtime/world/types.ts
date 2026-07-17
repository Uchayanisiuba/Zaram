// desktop/src/runtime/world/types.ts
//
// Milestone 1.3 — World Runtime type contracts.
//
// The World Runtime aggregates "system perception" — the discrete, observable
// state of the environment the AI lives in (desktop, applications, OS,
// notifications) — into a single immutable WorldState. It is an Intelligence
// Runtime: it is fully decoupled from the drawing layer and the character
// projection pipeline, and it never produces a FrameState.
//
// Every snapshot type below is a plain data structure. The runtime never hands
// out mutable references; consumers receive frozen deep copies (see
// world-runtime.ts). The Attention Runtime consumes the World only through the
// IWorldStateProvider / IWorldState interfaces declared here — it never depends
// on the concrete WorldRuntime.

import { clampUnit } from '../types'

// --- EnvironmentSnapshot ---------------------------------------------------
//
// The physical/logical environment the AI inhabits: where it is shown, how
// much space it has, whether it is foregrounded, and ambient context.

export type EnvironmentTheme = 'light' | 'dark' | 'system'
export type EnvironmentVisibility = 'visible' | 'occluded' | 'minimized' | 'hidden'

export interface EnvironmentSnapshot {
  // The viewport the presence is rendered into, normalised 0..1.
  viewport: { width: number; height: number }
  // Device pixel ratio (for crispness, never used for rendering here).
  devicePixelRatio: number
  // Is the host application the active foreground app?
  isForeground: boolean
  // Coarse visibility of the presence window.
  visibility: EnvironmentVisibility
  // Active OS theme.
  theme: EnvironmentTheme
  // 0 (completely obscured) .. 1 (fully visible).
  occlusion: number
  // Normalised pointer position in the environment, [-1,1] x/y (0,0 = center).
  pointer: { x: number; y: number }
  // Normalised primary display bounds the presence may reason about, 0..1.
  displayBounds: { width: number; height: number }
  updatedAt: number
}

// --- DesktopState ----------------------------------------------------------
//
// The desktop shell the AI is running on. Pure environmental perception, not
// part of the character pipeline.

export type DesktopPlatform = 'win32' | 'darwin' | 'linux' | 'unknown'
export type DesktopPowerState = 'active' | 'idle' | 'sleeping' | 'locked'

export interface DesktopState {
  platform: DesktopPlatform
  // OS-level idle/lock state.
  power: DesktopPowerState
  // 0 (just used) .. 1 (long idle). Derived from last input time.
  idleLevel: number
  // Number of physical/logical displays.
  displayCount: number
  // Total work-area in normalised units (0..1 scale, summed).
  workArea: { width: number; height: number }
  // Whether the user is actively interacting with the desktop right now.
  userActive: boolean
  updatedAt: number
}

// --- ApplicationState ------------------------------------------------------
//
// The host application (the Zaram app) and the foreground application the user
// is focused on. This is "what is the user doing" perception.

export interface ApplicationState {
  // Host application version/build identity.
  hostVersion: string
  // Whether the host app is foregrounded (mirrors environment.isForeground).
  hostFocused: boolean
  // The external application the user currently has focused, if known.
  foregroundApp: {
    name: string
    bundleId: string
    // 0 (background) .. 1 (fully focused by the user).
    focus: number
  } | null
  // Open document / conversation title the user is working in, if any.
  activeDocument: string | null
  // Whether the user is presently engaged in a conversation with the AI.
  conversationActive: boolean
  updatedAt: number
}

// --- SystemState -----------------------------------------------------------
//
// Discrete OS/runtime system state: load, connectivity, time-of-day. This is
// the "world's vital signs", separate from the Animation Runtime's
// SystemRuntime which is about cognitive load for rendering.

export type SystemConnectivity = 'online' | 'offline' | 'limited'

export interface SystemState {
  // Coarse activity state of the system runtime.
  state: 'idle' | 'working' | 'thinking' | 'speaking' | 'error' | 'sleeping'
  // 0 (idle) .. 1 (saturated) machine/process load.
  load: number
  // Network connectivity of the system.
  connectivity: SystemConnectivity
  // Battery level 0..1 (1 = full / plugged in).
  battery: number
  // Local hour of day 0..23 (fractional) for ambient reasoning.
  localHour: number
  // Monotonic uptime seconds of the host process.
  uptimeSec: number
  updatedAt: number
}

// --- NotificationState -----------------------------------------------------
//
// Transient system notifications competing for the AI's (and user's)
// attention. Salience decays over time; the World Runtime models that decay on
// the existing frame tick rather than spawning timers.

export interface NotificationItem {
  id: string
  // Short label.
  title: string
  // Coarse category for prioritisation.
  category: 'info' | 'message' | 'alert' | 'system'
  // 0 (trivial) .. 1 (critical).
  severity: number
  // When first observed (epoch ms).
  arrivedAt: number
  // 0 (faded) .. 1 (fresh) — computed by the runtime as it decays.
  salience: number
}

export interface NotificationState {
  // Active, non-expired notifications, most salient first.
  active: NotificationItem[]
  // Highest salience among active notifications (0 if none).
  peakSalience: number
  // Count of notifications delivered this session.
  totalDelivered: number
  updatedAt: number
}

// --- WorldState (immutable aggregate) --------------------------------------
//
// The full, read-only perception of the world at a point in time. The World
// Runtime returns a frozen deep copy of this on every read; consumers MUST NOT
// mutate it.

export interface WorldState {
  // Increasing revision so consumers can cheaply detect change.
  revision: number
  // Epoch ms when this snapshot was produced.
  timestamp: number
  environment: EnvironmentSnapshot
  desktop: DesktopState
  application: ApplicationState
  system: SystemState
  notification: NotificationState
}

// --- World events ----------------------------------------------------------
//
// The World Runtime publishes discrete world events to subscribers. These are
// in-process pub/sub (no external Event Bus dependency, fully decoupled from
// the drawing layer).
// They follow the same spirit as the frozen Event Bus contract: small, typed,
// and payload-immutable.

export type WorldEventType =
  | 'world.environment_changed'
  | 'world.desktop_changed'
  | 'world.application_changed'
  | 'world.system_changed'
  | 'world.notification_arrived'
  | 'world.notification_cleared'
  | 'world.foreground_changed'
  | 'world.visibility_changed'

export interface WorldEvent {
  type: WorldEventType
  // Monotonic event sequence.
  eventId: number
  timestamp: number
  // The relevant slice of world state at emit time (frozen copy).
  data: Partial<WorldState>
  // Optional correlation id linking to the originating perception feed.
  correlationId?: string
}

export type WorldEventListener = (event: Readonly<WorldEvent>) => void

// --- IWorldState: the interface Attention Runtime consumes -----------------
//
// The Attention Runtime depends ONLY on this interface. It receives read-only,
// immutable world snapshots and subscribes to world events. It never imports
// the concrete WorldRuntime, and stays decoupled from the drawing layer and the
// character projection pipeline.

export interface IWorldState {
  /** Immutable, frozen snapshot of the whole world right now. */
  getWorldState(): Readonly<WorldState>
  /** Immutable, frozen environment slice. */
  getEnvironment(): Readonly<EnvironmentSnapshot>
  /** Immutable, frozen desktop slice. */
  getDesktop(): Readonly<DesktopState>
  /** Immutable, frozen application slice. */
  getApplication(): Readonly<ApplicationState>
  /** Immutable, frozen system slice. */
  getSystem(): Readonly<SystemState>
  /** Immutable, frozen notification slice. */
  getNotification(): Readonly<NotificationState>
}

export interface IWorldStateProvider extends IWorldState {
  /** Subscribe to world events; returns an unsubscribe function. */
  subscribe(listener: WorldEventListener): () => void
  /** Advance salience decay / time-based evolution on the existing tick. */
  update(dt: number): void
}

// --- Helpers ---------------------------------------------------------------

export function clampOcclusion(value: number): number {
  return clampUnit(value)
}

export function defaultEnvironment(now: number = Date.now()): EnvironmentSnapshot {
  return {
    viewport: { width: 1, height: 1 },
    devicePixelRatio: 1,
    isForeground: true,
    visibility: 'visible',
    theme: 'system',
    occlusion: 1,
    pointer: { x: 0, y: 0 },
    displayBounds: { width: 1, height: 1 },
    updatedAt: now
  }
}

export function defaultDesktop(now: number = Date.now()): DesktopState {
  return {
    platform: 'unknown',
    power: 'active',
    idleLevel: 0,
    displayCount: 1,
    workArea: { width: 1, height: 1 },
    userActive: true,
    updatedAt: now
  }
}

export function defaultApplication(now: number = Date.now()): ApplicationState {
  return {
    hostVersion: '0.0.0',
    hostFocused: true,
    foregroundApp: null,
    activeDocument: null,
    conversationActive: false,
    updatedAt: now
  }
}

export function defaultSystem(now: number = Date.now()): SystemState {
  return {
    state: 'idle',
    load: 0.1,
    connectivity: 'online',
    battery: 1,
    localHour: 12,
    uptimeSec: 0,
    updatedAt: now
  }
}

export function defaultNotification(now: number = Date.now()): NotificationState {
  return {
    active: [],
    peakSalience: 0,
    totalDelivered: 0,
    updatedAt: now
  }
}

export function defaultWorldState(): WorldState {
  const now = Date.now()
  return {
    revision: 0,
    timestamp: now,
    environment: defaultEnvironment(now),
    desktop: defaultDesktop(now),
    application: defaultApplication(now),
    system: defaultSystem(now),
    notification: defaultNotification(now)
  }
}

// Deep-freeze a value so consumers cannot mutate the immutable snapshots the
// World Runtime hands out. Treats plain objects/arrays only; runtime data is
// always JSON-safe plain structures.
export function deepFreeze<T>(value: T): T {
  if (value === null || typeof value !== 'object') return value
  if (Object.isFrozen(value)) return value
  Object.freeze(value)
  for (const key of Object.keys(value as Record<string, unknown>)) {
    deepFreeze((value as Record<string, unknown>)[key])
  }
  return value
}
