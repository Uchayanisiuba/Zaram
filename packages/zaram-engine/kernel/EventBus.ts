// packages/zaram-engine/kernel/EventBus.ts
//
// Event-driven event bus for the Runtime Kernel.
// Zero dependencies, pure TypeScript.

import { RuntimeEvent, RuntimeEventName, EventListener, EventFilter, Disposable } from './types';

export class EventBus {
  private listeners: Map<RuntimeEventName, Set<EventListener>> = new Map();
  private filters: Map<RuntimeEventName, Set<EventFilter>> = new Map();
  private allListeners: Set<EventListener> = new Set();
  private eventLog: RuntimeEvent[] = [];
  private maxLogSize = 1000;
  private isLogging = false;

  subscribe(name: RuntimeEventName, listener: EventListener): Disposable {
    let set = this.listeners.get(name);
    if (!set) {
      set = new Set();
      this.listeners.set(name, set);
    }
    set.add(listener);
    return () => {
      set!.delete(listener);
      if (set!.size === 0) {
        this.listeners.delete(name);
      }
    };
  }

  subscribeAll(listener: EventListener): Disposable {
    this.allListeners.add(listener);
    return () => {
      this.allListeners.delete(listener);
    };
  }

  addFilter(name: RuntimeEventName, filter: EventFilter): Disposable {
    let set = this.filters.get(name);
    if (!set) {
      set = new Set();
      this.filters.set(name, set);
    }
    set.add(filter);
    return () => {
      set!.delete(filter);
      if (set!.size === 0) {
        this.filters.delete(name);
      }
    };
  }

  emit(event: Omit<RuntimeEvent, 'timestamp' | 'correlationId'> & {
    timestamp?: number;
    correlationId?: string;
  }): void {
    const fullEvent: RuntimeEvent = {
      ...event,
      timestamp: event.timestamp ?? Date.now(),
      correlationId: event.correlationId ?? this.generateCorrelationId(),
    };

    if (this.isLogging) {
      this.eventLog.push(fullEvent);
      if (this.eventLog.length > this.maxLogSize) {
        this.eventLog.shift();
      }
    }

    const filters = this.filters.get(fullEvent.name);
    if (filters && filters.size > 0) {
      for (const filter of filters) {
        if (!filter(fullEvent)) {
          return;
        }
      }
    }

    const listeners = this.listeners.get(fullEvent.name);
    if (listeners) {
      for (const listener of listeners) {
        try {
          listener(fullEvent);
        } catch (err) {
          console.error(`[EventBus] Error in listener for "${fullEvent.name}":`, err);
        }
      }
    }

    for (const listener of this.allListeners) {
      try {
        listener(fullEvent);
      } catch (err) {
        console.error(`[EventBus] Error in global listener:`, err);
      }
    }
  }

  emitAsync(event: Omit<RuntimeEvent, 'timestamp' | 'correlationId'> & {
    timestamp?: number;
    correlationId?: string;
  }): Promise<void> {
    return new Promise((resolve) => {
      setImmediate(() => {
        this.emit(event);
        resolve();
      });
    });
  }

  waitFor(name: RuntimeEventName, timeoutMs?: number): Promise<RuntimeEvent> {
    return new Promise((resolve, reject) => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      const disposable = this.subscribe(name, (event) => {
        if (timer) clearTimeout(timer);
        disposable();
        resolve(event);
      });

      if (timeoutMs !== undefined) {
        timer = setTimeout(() => {
          disposable();
          reject(new Error(`Timeout waiting for event: ${name}`));
        }, timeoutMs);
      }
    });
  }

  getEventLog(): RuntimeEvent[] {
    return [...this.eventLog];
  }

  clearEventLog(): void {
    this.eventLog = [];
  }

  setLogging(enabled: boolean, maxLogSize = 1000): void {
    this.isLogging = enabled;
    this.maxLogSize = maxLogSize;
  }

  getListenerCount(name?: RuntimeEventName): number {
    if (name) {
      return this.listeners.get(name)?.size ?? 0;
    }
    let total = 0;
    for (const set of this.listeners.values()) {
      total += set.size;
    }
    return total + this.allListeners.size;
  }

  private generateCorrelationId(): string {
    return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
  }
}

export const eventBus = new EventBus();