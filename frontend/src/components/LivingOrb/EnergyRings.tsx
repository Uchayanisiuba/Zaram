import { useEffect, useRef } from 'react';
import { useOrbState } from './useOrbState';

export function EnergyRings() {
  const { audioLevel, getColors } = useOrbState();
  const audioLevelRef = useRef(audioLevel);
  const animationRef = useRef<number>();
  const timeRef = useRef(0);
  const pathRefs = useRef<(SVGPathElement | null)[]>([]);

  useEffect(() => {
    audioLevelRef.current = audioLevel;
  }, [audioLevel]);

  useEffect(() => {
    const colors = getColors();
    
    const ringConfigs = [
      { radius: 140, phase: 0, frequency: 2, amplitude: 5, speed: 0.02, color: colors.primary, dash: '0', width: 1, rotate: false },
      { radius: 160, phase: Math.PI / 3, frequency: 3, amplitude: 7.5, speed: 0.015, color: colors.secondary, dash: '4 8', width: 1.5, rotate: true },
      { radius: 180, phase: Math.PI / 1.5, frequency: 1.5, amplitude: 10, speed: 0.025, color: colors.glow, dash: '2 6', width: 2, rotate: true },
      { radius: 200, phase: Math.PI, frequency: 2.5, amplitude: 6, speed: 0.018, color: colors.primary, dash: '0', width: 1, rotate: false },
    ];

    const animate = () => {
      timeRef.current += 1;
      const time = timeRef.current;
      const currentAudio = audioLevelRef.current;
      
      // CONSTANT PULSATION: Subtle sine wave breathing effect
      const breathe = Math.sin(time * 0.02) * 3; 

      ringConfigs.forEach((config, index) => {
        const pathEl = pathRefs.current[index];
        if (!pathEl) return;

        const points = [];
        const segments = 120;

        // Combine base wave, audio reactivity, and constant breathing
        const dynamicAmplitude = config.amplitude + (currentAudio * 30) + breathe;
        const dynamicSpeed = config.speed + (currentAudio * 0.04);

        for (let i = 0; i <= segments; i++) {
          const angle = (i / segments) * Math.PI * 2;
          const baseX = 300 + Math.cos(angle) * config.radius;
          const baseY = 300 + Math.sin(angle) * config.radius;
          const wave = Math.sin(angle * config.frequency + time * dynamicSpeed + config.phase) * dynamicAmplitude;
          const offsetX = Math.cos(angle + Math.PI / 2) * wave;
          const offsetY = Math.sin(angle + Math.PI / 2) * wave;
          points.push(`${baseX + offsetX},${baseY + offsetY}`);
        }

        pathEl.setAttribute('d', `M ${points.join(' L ')} Z`);
        pathEl.setAttribute('stroke', config.color);
        pathEl.setAttribute('stroke-width', config.width.toString());
        pathEl.setAttribute('stroke-dasharray', config.dash);
        
        // Base opacity + audio reactivity + subtle breathing
        const baseOpacity = 0.3 + (Math.sin(time * 0.015) * 0.1);
        pathEl.setAttribute('opacity', `${baseOpacity + (currentAudio * 0.5)}`);
        pathEl.style.filter = `drop-shadow(0 0 ${2 + currentAudio * 10 + breathe}px ${config.color})`;

        if (config.rotate) {
          const rotation = (time * 0.15) % 360;
          pathEl.style.transform = `rotate(${rotation}deg)`;
          pathEl.style.transformOrigin = '300px 300px';
        } else {
          pathEl.style.transform = '';
        }
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();
    return () => { if (animationRef.current) cancelAnimationFrame(animationRef.current); };
  }, [getColors]);

  return (
    <svg className="absolute inset-0 pointer-events-none" viewBox="0 0 600 600" style={{ mixBlendMode: 'screen' }}>
      {[0, 1, 2, 3].map((i) => (
        <path key={i} ref={(el) => { pathRefs.current[i] = el; }} fill="none" strokeLinecap="round" strokeLinejoin="round" />
      ))}
    </svg>
  );
}