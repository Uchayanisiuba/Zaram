// desktop/src/runtime/event-bus.ts
//
// Central Event Bus for the Zaram OS.
// All subsystems communicate through this bus — no direct coupling.
// Event-driven, async-safe, ordered delivery.

import type { ZaramEvent, ZaramEventType,
  ExecutiveIntentChangedData,
  ExecutiveStateChangedData,
  ConversationPhaseChangedData,
  PresenceStateChangedData,
  SpeechSynthesisData,
  KnowledgeSearchData
} from './types'

// UUID generator that works in both Node.js (main process) and browser (renderer)
function generateUUID(): string {
  // Try Web Crypto API first (browser, Electron renderer)
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  // Fallback for Node.js (Electron main process)
  try {
    const nodeCrypto = require('crypto')
    return nodeCrypto.randomUUID()
  } catch {
    // Last resort: simple UUID v4
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0
      const v = c === 'x' ? r : (r & 0x3) | 0x8
      return v.toString(16)
    })
  }
}

type EventCallback = (event: ZaramEvent) => void | Promise<void>

export class EventBus {
  private subscribers = new Map<ZaramEventType, Set<EventCallback>>()
  private history: ZaramEvent[] = []
  private readonly maxHistory = 500

  subscribe(eventType: ZaramEventType, callback: EventCallback): () => void {
    let set = this.subscribers.get(eventType)
    if (!set) {
      set = new Set()
      this.subscribers.set(eventType, set)
    }
    set.add(callback)

    return () => {
      set?.delete(callback)
    }
  }

  subscribeAll(callback: EventCallback): () => void {
    const unsubscribers: (() => void)[] = []
    for (const eventType of this.subscribers.keys()) {
      unsubscribers.push(this.subscribe(eventType, callback))
    }
    return () => {
      for (const unsub of unsubscribers) unsub()
    }
  }

  publish(eventType: ZaramEventType, data: Record<string, unknown>, sourceRuntime?: string, correlationId?: string): void {
    const event: ZaramEvent = {
      event_id: generateUUID(),
      timestamp: Date.now(),
      source_runtime: sourceRuntime ?? 'system',
      event_type: eventType,
      version: 1,
      priority: 'normal',
      data,
      correlation_id: correlationId ?? '',
    }
    this.publishEvent(event)
  }

  publishEvent(event: ZaramEvent): void {
    this.history.push(event)
    if (this.history.length > this.maxHistory) {
      this.history.shift()
    }

    const callbacks = this.subscribers.get(event.event_type)
    if (!callbacks) return

    for (const callback of callbacks) {
      try {
        const result = callback(event)
        if (result && typeof result.then === 'function') {
          // Fire and forget - errors handled by caller
          result.catch(err => console.error('[EventBus] Async subscriber error:', err))
        }
      } catch (err) {
        console.error('[EventBus] Subscriber error:', err)
      }
    }
  }

  getHistory(eventType?: ZaramEventType, limit = 50): ZaramEvent[] {
    let events = this.history
    if (eventType) {
      events = events.filter(e => e.event_type === eventType)
    }
    return events.slice(-limit)
  }

  subscriberCount(eventType: ZaramEventType): number {
    const set = this.subscribers.get(eventType)
    return set ? set.size : 0
  }

  clearHistory(): void {
    this.history = []
  }
}

// Global singleton instance
export const eventBus = new EventBus()

// Re-export types for convenience
export type {
  ExecutiveIntentChangedData,
  ExecutiveStateChangedData,
  ConversationPhaseChangedData,
  PresenceStateChangedData,
  SpeechSynthesisData,
  KnowledgeSearchData,
  ZaramEventType
}