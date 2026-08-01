import { useOrbStore } from '../stores/orbStore';

export const useOrb = () => {
  const orbState = useOrbStore((state) => state.orbState);
  const setOrbState = useOrbStore((state) => state.setOrbState);

  return { orbState, setOrbState };
};