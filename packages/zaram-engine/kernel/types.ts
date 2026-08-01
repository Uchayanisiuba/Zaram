// packages/zaram-engine/kernel/types.ts
//
// Core type definitions for the Runtime Kernel.
// No UI, no React, no Three.js — pure OS kernel types.

export type RuntimePhase =
  | 'uninitialized'
  | 'initializing'
  | 'ready'
  | 'running'
  | 'pausing'
  | 'paused'
  | 'stopping'
  | 'stopped'
  | 'error';

export type RuntimeEventName =
  | 'kernel.boot'
  | 'kernel.ready'
  | 'kernel.shutdown'
  | 'kernel.error'
  | 'runtime.start'
  | 'runtime.stop'
  | 'runtime.pause'
  | 'runtime.resume'
  | 'runtime.error'
  | 'service.register'
  | 'service.unregister'
  | 'service.start'
  | 'service.stop'
  | 'service.error'
  | 'dependency.resolve'
  | 'dependency.missing'
  | 'hotreload.start'
  | 'hotreload.complete'
  | 'hotreload.error'
  | string;

export interface RuntimeEvent {
  readonly name: RuntimeEventName;
  readonly payload: unknown;
  readonly timestamp: number;
  readonly correlationId: string;
  readonly source: string;
}

export interface ServiceDescriptor {
  readonly id: string;
  readonly name: string;
  readonly version: string;
  readonly dependencies: string[];
  readonly optionalDependencies: string[];
  readonly priority: number;
  readonly singleton: boolean;
  readonly hotReloadable: boolean;
  readonly factory: () => Promise<unknown> | unknown;
  readonly dispose?: (instance: unknown) => Promise<void> | void;
  readonly healthCheck?: () => Promise<boolean> | boolean;
}

export interface ServiceInstance {
  readonly id: string;
  readonly descriptor: ServiceDescriptor;
  instance: unknown;
  state: 'registered' | 'starting' | 'running' | 'stopping' | 'stopped' | 'error';
  readonly startTime?: number;
  readonly stopTime?: number;
  error?: Error;
}

export interface DependencyNode {
  readonly id: string;
  readonly dependencies: Set<string>;
  readonly dependents: Set<string>;
  readonly depth: number;
}

export interface RuntimeHealth {
  readonly phase: RuntimePhase;
  readonly uptime: number;
  readonly services: number;
  readonly servicesRunning: number;
  readonly servicesError: number;
  readonly dependencyGraph: {
    nodes: number;
    edges: number;
    cycles: string[][];
  };
  readonly lastError?: {
    timestamp: number;
    serviceId: string;
    error: string;
  };
}

export interface BootSequence {
  readonly steps: BootStep[];
  readonly currentStep: number;
  readonly completed: boolean;
  readonly failed: boolean;
  readonly error?: Error;
}

export interface BootStep {
  readonly name: string;
  readonly serviceIds: string[];
  readonly required: boolean;
  readonly completed: boolean;
  readonly error?: Error;
}

export interface HotReloadResult {
  readonly serviceId: string;
  readonly success: boolean;
  readonly error?: Error;
  readonly timestamp: number;
}

export type EventListener = (event: RuntimeEvent) => void;
export type EventFilter = (event: RuntimeEvent) => boolean;
export type Disposable = () => void;