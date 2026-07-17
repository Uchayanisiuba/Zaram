// desktop/src/runtime/sources/base.ts
//
// Minimal event-driven source base. Runtime sources hold state, notify on
// change, and carry no timers (the Animation Runtime owns the tick loop).

export abstract class BaseSource<T> {
  private readonly listeners = new Set<(snapshot: T) => void>()
  private running = false

  abstract getSnapshot(): T

  subscribe(listener: (snapshot: T) => void): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  start(): void {
    this.running = true
  }

  stop(): void {
    this.running = false
  }

  protected emit(): void {
    if (!this.running) return
    const snapshot = this.getSnapshot()
    this.listeners.forEach((listener) => listener(snapshot))
  }
}
