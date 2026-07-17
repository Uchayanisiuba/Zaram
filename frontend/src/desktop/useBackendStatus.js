import { useEffect, useState } from 'react';
import { desktop } from './bridge';

/**
 * Subscribes to backend connection status from the desktop host.
 *
 * Non-visual: returns the latest status so a component may choose to render an
 * indicator. Safe in a plain browser (resolves to `unavailable` with no host).
 */
export function useBackendStatus() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    if (!desktop.isDesktop) {
      setStatus({ state: 'unavailable', error: 'Not running in desktop host' });
      return undefined;
    }
    let active = true;
    desktop.backend.getStatus().then((s) => {
      if (active) setStatus(s);
    });
    const off = desktop.backend.onStatus((s) => {
      if (active) setStatus(s);
    });
    return () => {
      active = false;
      off();
    };
  }, []);

  return status;
}

export default useBackendStatus;
