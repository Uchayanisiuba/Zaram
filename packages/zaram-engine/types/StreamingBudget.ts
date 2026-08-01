// packages/zaram-engine/types/StreamingBudget.ts

export type StreamingPriority = 'critical' | 'high' | 'medium' | 'low' | 'background';

export interface StreamingBudget {
  critical: number;
  high: number;
  medium: number;
  low: number;
  background: number;
}

export interface BudgetParams {
  cameraDistance: number;
  cameraVelocity: number;
  importance: number;
  screenSize: number;
}

export function computeBudget(params: BudgetParams): { tier: StreamingPriority; score: number } {
  const distanceScore = Math.max(0, 1 - params.cameraDistance / 500);
  const velocityScore = 1 - Math.min(1, params.cameraVelocity / 50);
  const importanceScore = params.importance;
  const screenScore = Math.min(1, params.screenSize / 1920);

  const score = distanceScore * 0.4 + velocityScore * 0.15 + importanceScore * 0.3 + screenScore * 0.15;

  if (score > 0.7) return { tier: 'critical', score };
  if (score > 0.5) return { tier: 'high', score };
  if (score > 0.3) return { tier: 'medium', score };
  if (score > 0.1) return { tier: 'low', score };
  return { tier: 'background', score };
}

export function createDefaultBudget(): StreamingBudget {
  return {
    critical: 4,
    high: 8,
    medium: 16,
    low: 32,
    background: 64
  };
}
