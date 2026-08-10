import { motion } from 'framer-motion';

const PARTICLES = [
  { top: '10%', left: '72%', delay: 0, size: 2.5, color: '#818cf8' },
  { top: '72%', left: '8%', delay: 0.7, size: 2, color: '#22d3ee' },
  { top: '28%', left: '4%', delay: 1.2, size: 2.5, color: '#c084fc' },
  { top: '5%', left: '38%', delay: 1.8, size: 1.5, color: '#818cf8' },
  { top: '84%', left: '58%', delay: 0.4, size: 2, color: '#22d3ee' },
  { top: '50%', left: '93%', delay: 1.5, size: 2, color: '#c084fc' },
  { top: '18%', left: '91%', delay: 1.0, size: 1.5, color: '#818cf8' },
  { top: '90%', left: '26%', delay: 2.0, size: 2, color: '#22d3ee' },
  { top: '42%', left: '2%', delay: 0.6, size: 1.5, color: '#c084fc' },
  { top: '64%', left: '88%', delay: 1.3, size: 2, color: '#818cf8' },
];

const FloatingParticles = () => {
  return (
    <>
      {PARTICLES.map((p, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full z-10 pointer-events-none"
          style={{
            width: p.size,
            height: p.size,
            top: p.top,
            left: p.left,
            background: p.color,
            boxShadow: `0 0 4px ${p.color}`,
          }}
          animate={{ y: [0, -12, 0], x: [0, 6, 0], opacity: [0.2, 0.9, 0.2] }}
          transition={{ duration: 3.5 + p.delay, repeat: Infinity, delay: p.delay, ease: 'easeInOut' }}
        />
      ))}
    </>
  );
};

export default FloatingParticles;