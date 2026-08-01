interface EventEnvelope<T = any> {
  eventId: string;          // UUID v4
  timestamp: number;        // Epoch ms
  source: string;           // e.g., 'BuildSurface', 'CommandPalette'
  topic: string;            // e.g., 'ai.synthesis.complete'
  priority: EventPriority;  // 'critical' | 'high' | 'normal' | 'low'
  payload: T;               // Strictly typed payload
  metadata?: Record<string, any>; // Optional tracing/debugging data
}