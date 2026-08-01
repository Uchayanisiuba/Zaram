import { motion } from 'framer-motion';

const barCount = 5;
const animationDuration = 0.8;

const WaveformBars = () => {
  return (
    <div className="flex items-center justify-center space-x-1 h-8">
      {Array.from({ length: barCount }).map((_, i) => (
        <motion.div
          key={i}
          className="w-1 bg-emerald-500 rounded-full"
          animate={{
            height: ['20%', '80%', '20%'],
          }}
          transition={{
            duration: animationDuration,
            repeat: Infinity,
            delay: i * (animationDuration / barCount / 2),
            ease: 'easeInOut',
          }}
        />
      ))}
    </div>
  );
};

export default WaveformBars;