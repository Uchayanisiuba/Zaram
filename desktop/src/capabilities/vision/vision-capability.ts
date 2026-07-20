// desktop/src/capabilities/vision/vision-capability.ts
//
// Milestone 2.1 — Vision Capability Pack.
//
// Implements ICapabilityPack. Registers 5 vision capability descriptors
// with the Capability Runtime and 5 handlers with the Execution Invoker.
// All vision capabilities delegate to the backend Ollama vision endpoint
// using Qwen2.5-VL 7B as the primary model.
//
// This pack is completely isolated. It does not import the drawing layer,
// the body layer, concrete avatars, the character projection, the animation
// engine, frame snapshots, the desktop shell, any GPU/3D engine, or the
// Emotion/Behaviour/Presence/Character/body-layer runtimes.

import type { ICapabilityRuntime } from '../../runtime/capability'
import type { IExecutionInvoker, ExecutionHandler, ExecutionRollback } from '../../runtime/execution'
import type { VisionHandlerContext, VisionMetrics } from './vision-types'
import { handleAnalyze, handleScreen, handleCamera, handleDocument, handleOCR, createVisionHandlers } from './vision-handler'

const VISION_CAPABILITIES: Array<{
  id: string
  name: string
  description: string
  category: 'vision'
  permissions: string[]
  latencyEstimateMs: number
}> = [
  {
    id: 'vision.analyze',
    name: 'Analyze Image',
    description: 'Analyze an image using Qwen2.5-VL vision model',
    category: 'vision',
    permissions: ['vision:analyze'],
    latencyEstimateMs: 2000,
  },
  {
    id: 'vision.screen',
    name: 'Analyze Screen',
    description: 'Capture and analyze the active screen or window',
    category: 'vision',
    permissions: ['vision:screen', 'desktop:capture'],
    latencyEstimateMs: 2500,
  },
  {
    id: 'vision.camera',
    name: 'Analyze Camera',
    description: 'Capture a single frame from the camera and analyze it',
    category: 'vision',
    permissions: ['vision:camera', 'media:camera'],
    latencyEstimateMs: 2000,
  },
  {
    id: 'vision.document',
    name: 'Analyze Document',
    description: 'Extract text and structure from document images',
    category: 'vision',
    permissions: ['vision:document'],
    latencyEstimateMs: 3000,
  },
  {
    id: 'vision.ocr',
    name: 'OCR',
    description: 'Optical character recognition on images',
    category: 'vision',
    permissions: ['vision:ocr'],
    latencyEstimateMs: 1500,
  },
]

export const DEFAULT_VISION_METRICS: VisionMetrics = {
  operationsExecuted: 0,
  analyzeCount: 0,
  screenCount: 0,
  cameraCount: 0,
  documentCount: 0,
  ocrCount: 0,
}

export class VisionCapabilityPack {
  private readonly subscribers = new Set<(event: { eventType: string; data: Record<string, unknown> }) => void>()
  private readonly metrics: VisionMetrics = { ...DEFAULT_VISION_METRICS }

  constructor(private readonly capabilityRuntime: ICapabilityRuntime) {}

  getMetrics(): VisionMetrics {
    return { ...this.metrics }
  }

  recordOperation(capabilityId: string): void {
    this.metrics.operationsExecuted += 1
    if (capabilityId === 'vision.analyze') this.metrics.analyzeCount += 1
    else if (capabilityId === 'vision.screen') this.metrics.screenCount += 1
    else if (capabilityId === 'vision.camera') this.metrics.cameraCount += 1
    else if (capabilityId === 'vision.document') this.metrics.documentCount += 1
    else if (capabilityId === 'vision.ocr') this.metrics.ocrCount += 1
  }

  registerHandlers(invoker: IExecutionInvoker): void {
    const emit = (eventType: string, data: Record<string, unknown>) => {
      this.publish(eventType, data)
    }
    const ctx = createVisionHandlers(emit, (capabilityId) => this.recordOperation(capabilityId))

    invoker.register('vision.analyze', wrapHandler(ctx, handleAnalyze(ctx)))
    invoker.register('vision.screen', wrapHandler(ctx, handleScreen(ctx)))
    invoker.register('vision.camera', wrapHandler(ctx, handleCamera(ctx)))
    invoker.register('vision.document', wrapHandler(ctx, handleDocument(ctx)))
    invoker.register('vision.ocr', wrapHandler(ctx, handleOCR(ctx)))
  }

  registerDescriptors(capabilityRuntime: ICapabilityRuntime): void {
    for (const cap of VISION_CAPABILITIES) {
      capabilityRuntime.register({
        id: cap.id,
        name: cap.name,
        description: cap.description,
        category: cap.category,
        permissions: cap.permissions as any,
        inputSchema: { type: 'object', properties: { prompt: { type: 'string' }, image: { type: 'string' } }, required: ['image'] },
        outputSchema: { type: 'object', properties: { response: { type: 'string' } } },
        availability: 'available',
        latencyEstimateMs: cap.latencyEstimateMs,
        location: 'local',
        cost: 0,
        enabled: true,
        source: 'vision-pack',
        tags: ['vision', 'multimodal', 'ollama']
      })
    }
  }

  subscribe(listener: (event: { eventType: string; data: Record<string, unknown> }) => void): () => void {
    this.subscribers.add(listener)
    return () => { this.subscribers.delete(listener) }
  }

  private publish(eventType: string, data: Record<string, unknown>): void {
    for (const listener of this.subscribers) {
      try { listener({ eventType, data }) } catch { /* subscriber errors must not break operations */ }
    }
  }
}

function wrapHandler(ctx: VisionHandlerContext, handler: ExecutionHandler): ExecutionHandler {
  return (req, c, controls) => {
    const result = handler(req, c, controls)
    if (result && typeof result.then === 'function') {
      return result.then((res) => {
        ctx.recordOperation(req.capabilityId)
        return res
      }).catch(() => {
        ctx.recordOperation(req.capabilityId)
      })
    }
    ctx.recordOperation(req.capabilityId)
    return result
  }
}

export function buildVisionRollback(): ExecutionRollback {
  return (_req, _ctx) => {
    // Vision operations are read-only; no rollback needed.
  }
}
