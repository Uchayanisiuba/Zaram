// desktop/src/runtime/world/world-runtime.ts
//
// Milestone 1.3 — World Runtime (Intelligence Runtime).
//
// Aggregates system perception into a single immutable WorldState and publishes
// world events. It is fully event-driven and time-evolved ONLY on the existing
// 30Hz frame tick (no setInterval, no requestAnimationFrame, no polling loop of
// its own). It is fully decoupled from the drawing layer and the character projection pipeline.
//
// The Attention Runtime consumes the world exclusively through IWorldState /
// IWorldStateProvider (see ./types.ts). It never sees the concrete runtime. It
// stays decoupled from the drawing layer and the character projection pipeline.

import { clampUnit } from '../types'
import {
  deepFreeze,
  defaultApplication,
  defaultDesktop,
  defaultEnvironment,
  defaultNotification,
  defaultSystem,
  type ApplicationState,
  type DesktopState,
  type EnvironmentSnapshot,
  type IWorldStateProvider,
  type NotificationItem,
  type NotificationState,
  type SystemState,
  type WorldEvent,
  type WorldEventListener,
  type WorldEventType,
  type WorldState
} from './types'

export interface WorldRuntimeOptions {
  // Per-second salience decay for notifications when not refreshed.
  notificationDecayPerSec?: number
  // Maximum number of notifications retained in the active list.
  maxNotifications?: number
  // Injectable clock (test hook).
  now?: () => number
}

export class WorldRuntime implements IWorldStateProvider {
  private readonly subscribers = new Set<WorldEventListener>()
  private readonly notificationDecayPerSec: number
  private readonly maxNotifications: number
  private readonly now: () => number

  private revision = 0
  private eventSeq = 0
  private environment: EnvironmentSnapshot = defaultEnvironment()
  private desktop: DesktopState = defaultDesktop()
  private application: ApplicationState = defaultApplication()
  private system: SystemState = defaultSystem()
  private notification: NotificationState = defaultNotification()

  constructor(options: WorldRuntimeOptions = {}) {
    this.notificationDecayPerSec = options.notificationDecayPerSec ?? 0.4
    this.maxNotifications = options.maxNotifications ?? 16
    this.now = options.now ?? (() => Date.now())
  }

  // --- Perception ingestion (called by injected sources) -------------------
  //
  // Each setter updates one slice, bumps the revision, and publishes a discrete
  // world event. No timers, no loops — these are push-based.

  setEnvironment(next: Partial<EnvironmentSnapshot>): void {
    const prev = this.environment
    this.environment = { ...prev, ...next, occlusion: clampUnit(next.occlusion ?? prev.occlusion), updatedAt: this.now() }
    if (prev.isForeground !== this.environment.isForeground) {
      this.publish('world.foreground_changed', { environment: this.environment })
    }
    if (prev.visibility !== this.environment.visibility) {
      this.publish('world.visibility_changed', { environment: this.environment })
    }
    this.publish('world.environment_changed', { environment: this.environment })
  }

  setDesktop(next: Partial<DesktopState>): void {
    this.desktop = { ...this.desktop, ...next, idleLevel: clampUnit(next.idleLevel ?? this.desktop.idleLevel), updatedAt: this.now() }
    this.publish('world.desktop_changed', { desktop: this.desktop })
  }

  setApplication(next: Partial<ApplicationState>): void {
    this.application = { ...this.application, ...next, updatedAt: this.now() }
    this.publish('world.application_changed', { application: this.application })
  }

  setSystem(next: Partial<SystemState>): void {
    this.system = { ...this.system, ...next, load: clampUnit(next.load ?? this.system.load), updatedAt: this.now() }
    this.publish('world.system_changed', { system: this.system })
  }

  // Deliver a new notification. Salience starts at the (clamped) severity.
  deliverNotification(input: {
    id: string
    title: string
    category?: NotificationItem['category']
    severity?: number
    correlationId?: string
  }): void {
    const severity = clampUnit(input.severity ?? 0.5)
    const item: NotificationItem = {
      id: input.id,
      title: input.title,
      category: input.category ?? 'info',
      severity,
      arrivedAt: this.now(),
      salience: severity
    }
    const active = [item, ...this.notification.active].slice(0, this.maxNotifications)
    this.notification = {
      active,
      peakSalience: Math.max(0, ...active.map((n) => n.salience)),
      totalDelivered: this.notification.totalDelivered + 1,
      updatedAt: this.now()
    }
    this.publish('world.notification_arrived', { notification: this.notification }, input.correlationId)
  }

  // Clear a notification by id (e.g. user dismissed it).
  clearNotification(id: string): void {
    const active = this.notification.active.filter((n) => n.id !== id)
    if (active.length === this.notification.active.length) return
    this.notification = {
      active,
      peakSalience: Math.max(0, ...active.map((n) => n.salience)),
      totalDelivered: this.notification.totalDelivered,
      updatedAt: this.now()
    }
    this.publish('world.notification_cleared', { notification: this.notification })
  }

  // --- Time evolution on the existing 30Hz tick ----------------------------
  //
  // Advances notification salience decay. Called by PresenceRuntime.tick(dt)
  // (the reused 30Hz scheduler). Introduces NO new timer or loop.

  update(dt: number): void {
    if (this.notification.active.length === 0) return
    let changed = false
    const active = this.notification.active.map((n) => {
      if (n.salience <= 0) return n
      changed = true
      const salience = Math.max(0, n.salience - this.notificationDecayPerSec * dt)
      return salience === 0 ? n : { ...n, salience }
    })
    if (!changed) return
    const pruned = active.filter((n) => n.salience > 0.001)
    this.notification = {
      active: pruned,
      peakSalience: pruned.length ? Math.max(...pruned.map((n) => n.salience)) : 0,
      totalDelivered: this.notification.totalDelivered,
      updatedAt: this.now()
    }
    this.bump()
    this.publish('world.notification_cleared', { notification: this.notification })
  }

  // --- Read-only, immutable snapshots (IWorldState) -------------------------

  getWorldState(): Readonly<WorldState> {
    return deepFreeze<WorldState>({
      revision: this.revision,
      timestamp: this.now(),
      environment: { ...this.environment },
      desktop: { ...this.desktop },
      application: { ...this.application },
      system: { ...this.system },
      notification: {
        ...this.notification,
        active: this.notification.active.map((n) => ({ ...n }))
      }
    })
  }

  getEnvironment(): Readonly<EnvironmentSnapshot> {
    return deepFreeze({ ...this.environment })
  }

  getDesktop(): Readonly<DesktopState> {
    return deepFreeze({ ...this.desktop })
  }

  getApplication(): Readonly<ApplicationState> {
    return deepFreeze({ ...this.application })
  }

  getSystem(): Readonly<SystemState> {
    return deepFreeze({ ...this.system })
  }

  getNotification(): Readonly<NotificationState> {
    return deepFreeze({
      ...this.notification,
      active: this.notification.active.map((n) => ({ ...n }))
    })
  }

  // --- Event publishing ----------------------------------------------------

  subscribe(listener: WorldEventListener): () => void {
    this.subscribers.add(listener)
    return () => {
      this.subscribers.delete(listener)
    }
  }

  private publish(type: WorldEventType, data: Partial<WorldState>, correlationId?: string): void {
    this.bump()
    const event: WorldEvent = {
      type,
      eventId: this.eventSeq++,
      timestamp: this.now(),
      data: deepFreeze(data),
      correlationId
    }
    this.subscribers.forEach((l) => l(event))
  }

  private bump(): void {
    this.revision += 1
  }
}
