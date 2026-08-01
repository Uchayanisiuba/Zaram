// ✅ DO
import { memo, useCallback } from 'react';
import { useOrbStore } from '@/stores/orb';

interface OrbProps {
  state: OrbState;
  onInteract: (action: OrbAction) => void;
}

export const Orb = memo(function Orb({ state, onInteract }: OrbProps) {
  const handleClick = useCallback(() => {
    onInteract('openPalette');
  }, [onInteract]);

  return (
    <button 
      className={cn('orb', `orb--${state}`)}
      onClick={handleClick}
      aria-label={`Zaram Orb, currently ${state}`}
    >
      {/* Content */}
    </button>
  );
});

//  DON'T
export function Orb({ state, onInteract }) {
  return (
    <div onClick={() => onInteract('openPalette')}>
      {/* No accessibility, no memoization */}
    </div>
  );
}