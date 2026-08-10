import { motion, AnimatePresence } from 'framer-motion';
import { useOrbStore } from '@/stores';
import { orbPulse } from '@/motion/presets';

const Pulse = () => {
  const { orbState } = useOrbStore();

  const showPulse = orbState === 'speaking';

  return (
    <AnimatePresence>
      {showPulse && (
        <motion.div
          className="absolute w-40 h-40 rounded-full border-2 border-presence-primary/70"
          variants={orbPulse}
          initial="initial"
          animate="animate"
          exit="exit"
        />
      )}
    </AnimatePresence>
  );
};

export default Pulse;