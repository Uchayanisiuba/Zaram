import { motion } from 'framer-motion';
import { useFullFrame } from '@/hooks/useFrameState';

const SpatialBackground = () => {
  const frame = useFullFrame();
  const isThinking = frame.system.state === 'Thinking';

  return (
    <div className="fixed inset-0" style={{ zIndex: -1, backgroundColor: 'var(--background)' }}>
      {/* Ambient Light */}
      <motion.div
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(circle at 50% 50%, var(--color-secondary) 0%, transparent 70%)',
          opacity: 0.15,
        }}
        animate={{ scale: [1, 1.15, 1] }}
        transition={{ duration: 25, repeat: Infinity, repeatType: 'mirror', ease: 'easeInOut' }}
      />
      {/* Energy Field */}
      <motion.div
        className="absolute inset-0"
        style={{
          backgroundImage: 'linear-gradient(to right, oklch(from var(--text-primary) l c h / 0.1) 1px, transparent 1px), linear-gradient(to bottom, oklch(from var(--text-primary) l c h / 0.1) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
        animate={{ opacity: isThinking ? 0.1 : 0.05 }}
        transition={{ duration: 1.5, ease: 'easeInOut' }}
      />
    </div>
  );
};

export default SpatialBackground;