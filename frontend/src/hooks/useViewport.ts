import { useEffect, useState } from 'react';

export interface Viewport {
  width: number;
  height: number;
}

function read(): Viewport {
  if (typeof window === 'undefined') return { width: 1280, height: 800 };
  return { width: window.innerWidth, height: window.innerHeight };
}

/**
 * Current viewport size, updated on resize.
 *
 * The conversation panel is a percentage of the width and the orb has to be
 * positioned against the space that leaves, so both need a real number rather
 * than a CSS unit — the orb's offset is a transform inside a scaled container
 * and cannot be expressed in `vw`.
 */
export function useViewport(): Viewport {
  const [viewport, setViewport] = useState<Viewport>(read);

  useEffect(() => {
    let frame = 0;
    const onResize = () => {
      // Coalesce bursts of resize events into one update per frame.
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setViewport(read()));
    };
    window.addEventListener('resize', onResize);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', onResize);
    };
  }, []);

  return viewport;
}

export default useViewport;
