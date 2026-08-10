import { motion, AnimatePresence } from 'framer-motion';
import { useOrbStore } from '@/stores';
import { orbRipple } from '@/motion/presets';

const RippleLayer = () => {
  const { orbState } = useOrbStore();

  const showRipple = orbState === 'thinking';

  return (
    <AnimatePresence>
      {showRipple && (
        <motion.div
          className="absolute w-32 h-32 rounded-full border-2 border-presence-primary/50"
          variants={orbRipple}
          initial="initial"
          animate="animate"
          exit="exit"
        />
      )}
    </AnimatePresence>
  );
};

export default RippleLayer;