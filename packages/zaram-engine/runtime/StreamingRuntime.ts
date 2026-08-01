// packages/zaram-engine/runtime/StreamingRuntime.ts
import { StreamingPriority, StreamingBudget, computeBudget, createDefaultBudget } from '../types/StreamingBudget';

export interface StreamingTask {
  id: string;
  assetId: string;
  priority: StreamingPriority;
  url: string;
  retries: number;
  maxRetries: number;
  abort: AbortController;
  progress: number;
  status: 'pending' | 'loading' | 'complete' | 'error';
}

export interface StreamingQueueConfig {
  budgets: StreamingBudget;
  maxConcurrent: number;
}

export class StreamingRuntime {
  private readonly queue: StreamingTask[] = [];
  private readonly active = new Map<string, StreamingTask>();
  private readonly cache = new Map<string, { buffer: ArrayBuffer; size: number }>();
  private readonly sizes = new Map<string, number>();
  private config: StreamingQueueConfig = {
    budgets: createDefaultBudget(),
    maxConcurrent: 4
  };
  private memoryBudget = 256 * 1024 * 1024;
  private usedMemory = 0;

  configure(config: Partial<StreamingQueueConfig>): void {
    this.config = { ...this.config, ...config };
  }

  setMemoryBudget(bytes: number): void {
    this.memoryBudget = bytes;
  }

  enqueue(task: Omit<StreamingTask, 'id'>): string {
    const id = generateId();
    const full: StreamingTask = { ...task, id, status: 'pending', progress: 0 };
    this.queue.push(full);
    return id;
  }

  cancel(id: string): boolean {
    const idx = this.queue.findIndex(t => t.id === id);
    if (idx !== -1) {
      this.queue.splice(idx, 1);
      const active = this.active.get(id);
      if (active) {
        active.abort.abort();
        this.active.delete(id);
      }
      return true;
    }
    const active = this.active.get(id);
    if (active) {
      active.abort.abort();
      this.active.delete(id);
      return true;
    }
    return false;
  }

  retry(id: string): boolean {
    const task = this.findTask(id);
    if (!task || task.maxRetries <= task.retries) return false;
    task.retries++;
    task.status = 'pending';
    task.progress = 0;
    task.abort = new AbortController();
    this.queue.push(task);
    return true;
  }

  update(dt: number): { loaded: string[]; failed: string[] } {
    const loaded: string[] = [];
    const failed: string[] = [];

    const budget = this.config.budgets;
    const counts = { critical: 0, high: 0, medium: 0, low: 0, background: 0 };
    for (const t of this.active.values()) {
      if (t.status === 'loading') counts[t.priority]++;
    }

    const slots = this.config.maxConcurrent - this.active.size;
    for (let i = 0; i < slots && this.queue.length > 0; i++) {
      const task = this.queue.shift()!;
      if (counts[task.priority] >= budget[task.priority]) {
        this.queue.unshift(task);
        break;
      }
      task.status = 'loading';
      this.active.set(task.id, task);
    }

    for (const [, task] of this.active) {
      if (task.status === 'loading') {
        task.progress = Math.min(1, task.progress + dt * 0.5);
        if (task.progress >= 1) {
          task.status = 'complete';
          loaded.push(task.id);
          this.cache.set(task.assetId, { buffer: new ArrayBuffer(1024), size: 1024 });
          this.sizes.set(task.assetId, 1024);
          this.usedMemory += 1024;
          this.evictMemory();
        }
      }
    }

    for (const [id, task] of this.active) {
      if (task.status === 'complete') {
        this.active.delete(id);
      }
    }

    return { loaded, failed };
  }

  getQueuedCount(): number {
    return this.queue.length;
  }

  getActiveCount(): number {
    return this.active.size;
  }

  getMemoryUsage(): { used: number; budget: number } {
    return { used: this.usedMemory, budget: this.memoryBudget };
  }

  private findTask(id: string): StreamingTask | undefined {
    return this.queue.find(t => t.id === id) ?? this.active.get(id);
  }

  private evictMemory(): void {
    while (this.usedMemory > this.memoryBudget && this.sizes.size > 0) {
      const first = this.sizes.keys().next().value as string | undefined;
      if (!first) break;
      const size = this.sizes.get(first) || 0;
      this.cache.delete(first);
      this.sizes.delete(first);
      this.usedMemory -= size;
    }
  }
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}
