import { create } from 'zustand';

interface RuntimeMetrics {
  gpuUsage: number;
  memoryUsageMB: number;
  memoryTotalMB: number;
  tokenCount: number;
  activeModel: string;
  isLocal: boolean;
  latencyMs: number;
}

interface RuntimeStore {
  metrics: RuntimeMetrics;
  isConnected: boolean;
  updateMetrics: (metrics: Partial<RuntimeMetrics>) => void;
  setConnected: (connected: boolean) => void;
}

export const useRuntimeStore = create<RuntimeStore>((set) => ({
  metrics: {
    gpuUsage: 0,
    memoryUsageMB: 0,
    memoryTotalMB: 16384,
    tokenCount: 0,
    activeModel: 'local',
    isLocal: true,
    latencyMs: 0,
  },
  isConnected: false,
  updateMetrics: (metrics) => 
    set((state) => ({ metrics: { ...state.metrics, ...metrics } })),
  setConnected: (connected) => set({ isConnected: connected }),
}));