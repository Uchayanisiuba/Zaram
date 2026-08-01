import { usePresenceStore } from '../stores/presenceStore';

export const usePresence = () => {
  const status = usePresenceStore((state) => state.status);
  const setStatus = usePresenceStore((state) => state.setStatus);

  return { status, setStatus };
};