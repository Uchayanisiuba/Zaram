import { motion, AnimatePresence } from 'framer-motion';
import { useOrbStore } from '@/stores';

const FocusRing = () => {
  const { orbState } = useOrbStore();

  return (
    <AnimatePresence>
      {orbState === 'listening' && (
        <motion.div
          className="absolute w-56 h-56 rounded-full border-4 border-presence-core"
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
        />
      )}
    </AnimatePresence>
  );
};

export default FocusRing;