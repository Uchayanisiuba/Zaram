import { create } from 'zustand';

type PresenceStatus = 'online' | 'away' | 'dnd' | 'offline';

interface PresenceStore {
  status: PresenceStatus;
  setStatus: (status: PresenceStatus) => void;
}

export const usePresenceStore = create<PresenceStore>((set) => ({
  status: 'online',
  setStatus: (status) => set({ status }),
}));