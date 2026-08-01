import { useDragControls } from 'framer-motion';

interface SurfaceHeaderProps {
  title: string;
  dragControls: ReturnType<typeof useDragControls>;
}

const SurfaceHeader = ({ title, dragControls }: SurfaceHeaderProps) => {
  const startDrag = (event: React.PointerEvent) => {
    dragControls.start(event, { snapToCursor: false });
  };

  return (
    <div
      className="flex h-10 cursor-grab items-center justify-between border-b border-white/10 px-4 active:cursor-grabbing"
      onPointerDown={startDrag}
    >
      <span className="text-sm text-neutral-400">{title}</span>
      <div className="flex items-center gap-2">
        <div className="h-3 w-3 rounded-full bg-white/20"></div>
        <div className="h-3 w-3 rounded-full bg-white/20"></div>
      </div>
    </div>
  );
};

export default SurfaceHeader;