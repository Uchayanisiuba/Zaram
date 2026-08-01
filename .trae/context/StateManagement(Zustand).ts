// ✅ DO
import { create } from 'zustand';

interface OrbState {
  state: OrbStateType;
  setState: (state: OrbStateType) => void;
  isListening: boolean;
  setListening: (listening: boolean) => void;
}

export const useOrbStore = create<OrbState>((set) => ({
  state: 'idle',
  setState: (state) => set({ state }),
  isListening: false,
  setListening: (listening) => set({ isListening: listening })
}));

// Usage
const { state, setState } = useOrbStore();

// ❌ DON'T
const [orbState, setOrbState] = useState('idle');