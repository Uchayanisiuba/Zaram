import { create } from 'zustand';

interface CameraState {
  x: number;
  y: number;
  zoom: number;
  setCamera: (x: number, y: number, zoom: number) => void;
}

export const useCameraStore = create<CameraState>((set) => ({
  x: 0,
  y: 0,
  zoom: 1,
  setCamera: (x, y, zoom) => set({ x, y, zoom }),
}));