import { create } from 'zustand';
import { FrameState, IDLE_FRAME } from '@/core/frame/types';

interface FrameStore {
  frame: FrameState;
  tick: number;
  updateFrame: (frame: FrameState) => void;
}

export const useFrameStore = create<FrameStore>((set) => ({
  frame: IDLE_FRAME,
  tick: 0,
  updateFrame: (frame) => set((state) => ({ 
    frame, 
    tick: state.tick + 1 
  })),
}));