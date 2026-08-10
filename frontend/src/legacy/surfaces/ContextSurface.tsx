import { motion, useDragControls } from 'framer-motion';
import { useSurfaceStore } from '@/stores/surfaceStore';
import { glass } from '@/theme/glass';
import { radius } from '@/theme/radius';
import { springPreset } from '@/motion/spring';
import SurfaceHeader from '@/components/surfaces/SurfaceHeader';
import SurfaceToolbar from '@/components/surfaces/SurfaceToolbar';
import SurfaceBody from '@/components/surfaces/SurfaceBody';

interface ContextSurfaceProps {
  id: string;
  title: string;
  zIndex: number;
  children: React.ReactNode;
}

const ContextSurface = ({ id, title, zIndex, children }: ContextSurfaceProps) => {
  const focusSurface = useSurfaceStore((state) => state.focusSurface);
  const updatePosition = useSurfaceStore((state) => state.updatePosition);
  const dragControls = useDragControls();

  return (
    <motion.div
      className="absolute flex w-[900px] h-[600px] flex-col rounded-lg shadow-lg"
      style={{
        background: glass.background,
        border: `1px solid ${glass.border}`,
        boxShadow: glass.shadow,
        backdropFilter: `blur(${glass.blur})`,
        borderRadius: radius.lg,
        zIndex,
      }}
      initial={{ scale: 0.95, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      exit={{ scale: 0.95, opacity: 0 }}
      transition={springPreset}
      dragListener={false}
      dragControls={dragControls}
      onPointerDown={() => focusSurface(id)}
      onDragEnd={(_, info) => {
        updatePosition(id, { x: info.point.x, y: info.point.y });
      }}
    >
      <SurfaceHeader title={title} dragControls={dragControls} />
      <SurfaceToolbar />
      <SurfaceBody>{children}</SurfaceBody>
    </motion.div>
  );
};

export default ContextSurface;