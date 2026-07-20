// desktop/src/capabilities/vision/vision-types.ts
//
// Milestone 2.1 — Vision Capability Pack types.
//

export interface VisionHandlerContext {
  emit: (eventType: string, data: Record<string, unknown>) => void
  recordOperation: (capabilityId: string) => void
}

export interface VisionMetrics {
  operationsExecuted: number
  analyzeCount: number
  screenCount: number
  cameraCount: number
  documentCount: number
  ocrCount: number
}

export const DEFAULT_VISION_METRICS: VisionMetrics = {
  operationsExecuted: 0,
  analyzeCount: 0,
  screenCount: 0,
  cameraCount: 0,
  documentCount: 0,
  ocrCount: 0,
}
