// desktop/tests/runtime/world/world-attention-adapter.test.ts
//
// Verifies the Attention Runtime consumes the World through the IWorldState
// *interface* only — via attentionEventFromWorld — and never needs the concrete
// WorldRuntime. We feed a hand-rolled mock implementing IWorldState and assert
// the derived AttentionEvent.

import { describe, it, expect } from 'vitest'
import { attentionEventFromWorld } from '../../../src/runtime/world'
import type { IWorldState, WorldState } from '../../../src/runtime/world'

function mockWorld(partial: Partial<WorldState>): IWorldState {
  const full: WorldState = {
    revision: 1,
    timestamp: Date.now(),
    environment: {
      viewport: { width: 1, height: 1 },
      devicePixelRatio: 1,
      isForeground: true,
      visibility: 'visible',
      theme: 'system',
      occlusion: 1,
      pointer: { x: 0, y: 0 },
      displayBounds: { width: 1, height: 1 },
      updatedAt: Date.now()
    },
    desktop: {
      platform: 'win32',
      power: 'active',
      idleLevel: 0,
      displayCount: 1,
      workArea: { width: 1, height: 1 },
      userActive: true,
      updatedAt: Date.now()
    },
    application: {
      hostVersion: '0.7.0',
      hostFocused: true,
      foregroundApp: null,
      activeDocument: null,
      conversationActive: false,
      updatedAt: Date.now()
    },
    system: {
      state: 'idle',
      load: 0.1,
      connectivity: 'online',
      battery: 1,
      localHour: 12,
      uptimeSec: 0,
      updatedAt: Date.now()
    },
    notification: { active: [], peakSalience: 0, totalDelivered: 0, updatedAt: Date.now() },
    ...partial
  }
  return {
    getWorldState: () => full,
    getEnvironment: () => full.environment,
    getDesktop: () => full.desktop,
    getApplication: () => full.application,
    getSystem: () => full.system,
    getNotification: () => full.notification
  }
}

describe('World -> Attention (interface-only consumption)', () => {
  it('pulls attention to notification when salience is high', () => {
    const world = mockWorld({
      notification: {
        active: [{ id: 'n1', title: 't', category: 'alert', severity: 0.9, arrivedAt: Date.now(), salience: 0.9 }],
        peakSalience: 0.9,
        totalDelivered: 1,
        updatedAt: Date.now()
      }
    })
    const ev = attentionEventFromWorld(world)
    expect(ev.target).toBe('notification')
    expect(ev.notification?.id).toBe('n1')
  })

  it('relaxes to internal when environment is occluded/backgrounded', () => {
    const world = mockWorld({ environment: { ...mockWorld({}).getEnvironment(), isForeground: false, occlusion: 0.1 } })
    const ev = attentionEventFromWorld(world)
    expect(ev.target).toBe('internal')
  })

  it('prefers conversation when a conversation is active', () => {
    const world = mockWorld({
      application: { ...mockWorld({}).getApplication(), conversationActive: true },
      notification: {
        active: [{ id: 'n1', title: 't', category: 'alert', severity: 0.9, arrivedAt: Date.now(), salience: 0.9 }],
        peakSalience: 0.9,
        totalDelivered: 1,
        updatedAt: Date.now()
      }
    })
    const ev = attentionEventFromWorld(world)
    expect(ev.target).toBe('conversation')
  })
})
