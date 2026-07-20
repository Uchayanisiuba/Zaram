import { motion, AnimatePresence } from 'framer-motion';
import { Send, Square, Mic } from 'lucide-react';

interface ActionButtonProps {
  onSend: () => void;
  onStop: () => void;
  onMic: () => void;
  isInputEmpty: boolean;
  state?: string;
}

export function ActionButton({ onSend, onStop, onMic, isInputEmpty, state = 'idle' }: ActionButtonProps) {
  const handleClick = () => {
    if (state === 'speaking' || state === 'generating' || state === 'thinking') {
      onStop();
    } else if (state === 'listening') {
      onMic();
    } else {
      onSend();
    }
  };

  return (
    <motion.button
      onClick={handleClick}
      className="relative flex items-center justify-center rounded-full transition-shadow duration-300"
      style={{
        background: state === 'idle' && isInputEmpty ? 'rgba(255,255,255,0.1)' : '#3b82f6',
        boxShadow: `0 0 20px rgba(59,130,246,0.5)`,
        width: '40px',
        height: '40px',
      }}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
    >
      <AnimatePresence mode="wait">
        {state === 'thinking' || state === 'generating' || state === 'speaking' ? (
          <motion.div
            key="stop"
            initial={{ scale: 0, rotate: -90 }}
            animate={{ scale: 1, rotate: 0 }}
            exit={{ scale: 0, rotate: 90 }}
            transition={{ duration: 0.2 }}
          >
            <Square size={16} className="text-black fill-black" />
          </motion.div>
        ) : state === 'listening' ? (
          <motion.div
            key="mic"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0 }}
            transition={{ duration: 0.2 }}
          >
            <Mic size={18} className="text-black animate-pulse" />
          </motion.div>
        ) : (
          <motion.div
            key="send"
            initial={{ scale: 0, rotate: 90 }}
            animate={{ scale: 1, rotate: 0 }}
            exit={{ scale: 0, rotate: -90 }}
            transition={{ duration: 0.2 }}
          >
            <Send size={18} className={isInputEmpty ? 'text-slate-400' : 'text-black'} />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.button>
  );
}