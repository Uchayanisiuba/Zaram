import React, { useRef } from 'react';
import { motion, useMotionValue } from 'framer-motion';
import { useWorkspaceStore } from '@/stores';

const Grid = () => (
  <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" className="absolute inset-0">
    <defs>
      <pattern id="smallGrid" width="16" height="16" patternUnits="userSpaceOnUse">
        <path d="M 16 0 L 0 0 0 16" fill="none" stroke="var(--neutral-700)" strokeWidth="0.5" />
      </pattern>
      <pattern id="grid" width="64" height="64" patternUnits="userSpaceOnUse">
        <rect width="64" height="64" fill="url(#smallGrid)" />
        <path d="M 64 0 L 0 0 0 64" fill="none" stroke="var(--neutral-600)" strokeWidth="1" />
      </pattern>
    </defs>
    <rect width="100%" height="100%" fill="url(#grid)" />
  </svg>
);

const SpatialRuntime = ({ children }: { children: React.ReactNode }) => {
  const { camera, setCamera } = useWorkspaceStore();
  const containerRef = useRef<HTMLDivElement>(null);

  const x = useMotionValue(camera.x);
  const y = useMotionValue(camera.y);
  const scale = useMotionValue(camera.zoom);

  const handlePan = (event: React.PointerEvent) => {
    if (event.buttons !== 4) return; // Middle mouse button
    const startX = x.get();
    const startY = y.get();

    const handlePointerMove = (e: PointerEvent) => {
      x.set(startX + e.clientX - event.clientX);
      y.set(startY + e.clientY - event.clientY);
    };

    const handlePointerUp = () => {
      setCamera({ x: x.get(), y: y.get() });
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  };

  const handleWheel = (event: React.WheelEvent) => {
    const delta = -event.deltaY / 1000;
    const newScale = Math.max(0.1, Math.min(2, scale.get() + delta));
    scale.set(newScale);
    setCamera({ zoom: newScale });
  };

  return (
    <div
      ref={containerRef}
      className="w-full h-full overflow-hidden relative cursor-grab active:cursor-grabbing"
      onPointerDown={handlePan}
      onWheel={handleWheel}
    >
      <Grid />
      <motion.div
        className="absolute"
        style={{ x, y, scale }}
      >
        {children}
      </motion.div>
    </div>
  );
};

export default SpatialRuntime;