import { useFrameStore } from '@/stores/frameStore';
import type { FrameState } from '@/core/frame/types';

// Selector hook — components use this to read specific frame properties
export function useFrameState<T>(selector: (frame: FrameState) => T): T {
  return useFrameStore((state) => selector(state.frame));
}

// Convenience: full frame (use sparingly, causes rerenders on every tick)
export function useFullFrame(): FrameState {
  return useFrameStore((state) => state.frame);
}