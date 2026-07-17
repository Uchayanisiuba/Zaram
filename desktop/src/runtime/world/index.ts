// desktop/src/runtime/world/index.ts
//
// Milestone 1.3 — World Runtime barrel.
//
// The World Runtime is an Intelligence Runtime that aggregates system
// perception into an immutable WorldState. It is consumed by the Attention
// Runtime through the IWorldState / IWorldStateProvider interfaces only. It
// stays fully decoupled from the drawing layer and the character pipeline.

export { WorldRuntime } from './world-runtime'
export type { WorldRuntimeOptions } from './world-runtime'

export { attentionEventFromWorld } from './world-attention-adapter'

export {
  deepFreeze,
  defaultWorldState,
  defaultEnvironment,
  defaultDesktop,
  defaultApplication,
  defaultSystem,
  defaultNotification,
  clampOcclusion
} from './types'
export type {
  WorldState,
  EnvironmentSnapshot,
  DesktopState,
  ApplicationState,
  SystemState,
  NotificationState,
  NotificationItem,
  WorldEvent,
  WorldEventType,
  WorldEventListener,
  IWorldState,
  IWorldStateProvider,
  EnvironmentTheme,
  EnvironmentVisibility,
  DesktopPlatform,
  DesktopPowerState,
  SystemConnectivity
} from './types'
