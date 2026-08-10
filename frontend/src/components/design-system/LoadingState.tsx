import { motion } from 'framer-motion';

const LoadingState = () => {
  return (
    <div className="flex items-center justify-center h-full">
      <motion.div
        style={{
          width: 24,
          height: 24,
          borderRadius: '50%',
          border: '2px solid rgba(255, 255, 255, 0.2)',
          borderTopColor: 'white',
        }}
        animate={{ rotate: 360 }}
        transition={{
          repeat: Infinity,
          ease: 'linear',
          duration: 1,
        }}
      />
    </div>
  );
};

export default LoadingState;