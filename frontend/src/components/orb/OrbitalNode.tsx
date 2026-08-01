import React from 'react';
import { motion, useMotionValue, useTransform } from 'framer-motion';
import { useAnimationFrame } from 'framer-motion';

interface OrbitalNodeProps {
  // The content of the node (e.g., an icon)
  children: React.ReactNode;
  // The radius of the orbit in pixels
  radius: number;
  // The duration of a full orbit in seconds
  duration: number;
  // An initial angle offset in degrees
  initialAngle?: number;
}

const OrbitalNode: React.FC<OrbitalNodeProps> = ({
  children,
  radius,
  duration,
  initialAngle = 0,
}) => {
  const angle = useMotionValue(initialAngle);

  useAnimationFrame((time) => {
    const newAngle = initialAngle + (time / (duration * 1000)) * 360;
    angle.set(newAngle);
  });

  const x = useTransform(angle, (a) => radius * Math.cos((a * Math.PI) / 180));
  const y = useTransform(angle, (a) => radius * Math.sin((a * Math.PI) / 180));

  return (
    <motion.div
      style={{
        position: 'absolute',
        x,
        y,
      }}
      className="w-16 h-16 bg-gray-700 rounded-full flex items-center justify-center"
    >
      {children}
    </motion.div>
  );
};

export default OrbitalNode;