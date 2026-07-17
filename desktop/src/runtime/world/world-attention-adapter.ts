// desktop/src/runtime/world/world-attention-adapter.ts
//
// Milestone 1.3 — World -> Attention mapping.
//
// The Attention Runtime consumes the World ONLY through the IWorldState
// interface. This pure adapter produces an AttentionEvent from an IWorldState
// snapshot so attention can react to environment/notification perception
// without ever depending on the concrete WorldRuntime. Importing this adapter
// does NOT pull in the WorldRuntime implementation — only the interface in
// ./types.ts.

import type { AttentionEvent } from '../cognitive/attention-runtime'
import type { IWorldState } from './types'

// Derive an AttentionEvent from the current (immutable) world snapshot.
// Notification salience pulls attention to 'notification'; an occluded or
// backgrounded environment relaxes attention toward 'internal'.
export function attentionEventFromWorld(world: IWorldState): AttentionEvent {
  const env = world.getEnvironment()
  const notif = world.getNotification()
  const app = world.getApplication()

  const event: AttentionEvent = {}

  if (notif.peakSalience > 0.5) {
    const top = notif.active[0]
    event.notification = { id: top?.id ?? 'unknown', severity: notif.peakSalience }
    event.target = 'notification'
  } else if (!env.isForeground || env.occlusion < 0.2) {
    event.target = 'internal'
  }

  if (app.conversationActive) {
    event.target = 'conversation'
  }

  return event
}
