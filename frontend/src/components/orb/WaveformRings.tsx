import { motion } from 'framer-motion';

const ringCount = 3;
const animationDuration = 2;

const WaveformRings = () => {
  return (
    <>
      {Array.from({ length: ringCount }).map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-full h-full rounded-full border-2 border-emerald-500"
          initial={{ scale: 0.5, opacity: 1 }}
          animate={{
            scale: 2,
            opacity: 0,
          }}
          transition={{
            duration: animationDuration,
            repeat: Infinity,
            delay: i * (animationDuration / ringCount),
            ease: 'easeOut',
          }}
        />
      ))}
    </>
  );
};

export default WaveformRings;