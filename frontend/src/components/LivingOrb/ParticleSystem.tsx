import { useEffect, useRef } from 'react';
import { useOrbState } from './useOrbState';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  size: number;
}

export function ParticleSystem() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { state, audioLevel, getColors } = useOrbState();
  const particlesRef = useRef<Particle[]>([]);
  const animationRef = useRef<number>();
  
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    canvas.width = 600;
    canvas.height = 600;
    
    const colors = getColors();
    
    const createParticle = (): Particle => {
      const angle = Math.random() * Math.PI * 2;
      const radius = 150 + Math.random() * 100;
      return {
        x: 300 + Math.cos(angle) * radius,
        y: 300 + Math.sin(angle) * radius,
        vx: (Math.random() - 0.5) * 2,
        vy: (Math.random() - 0.5) * 2,
        life: 0,
        maxLife: 100 + Math.random() * 100,
        size: 1 + Math.random() * 2,
      };
    };
    
    for (let i = 0; i < 100; i++) {
      particlesRef.current.push(createParticle());
    }
    
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      particlesRef.current.forEach((particle, index) => {
        particle.life++;
        
        const dx = particle.x - 300;
        const dy = particle.y - 300;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx);
        
        const orbitalSpeed = 0.02 + (audioLevel * 0.05);
        particle.vx += Math.cos(angle + Math.PI / 2) * orbitalSpeed;
        particle.vy += Math.sin(angle + Math.PI / 2) * orbitalSpeed;
        
        particle.x += particle.vx;
        particle.y += particle.vy;
        
        particle.vx *= 0.98;
        particle.vy *= 0.98;
        
        const lifeRatio = particle.life / particle.maxLife;
        const opacity = lifeRatio < 0.1 ? lifeRatio * 10 : lifeRatio > 0.9 ? (1 - lifeRatio) * 10 : 1;
        
        ctx.beginPath();
        ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
        ctx.fillStyle = `${colors.primary}${Math.floor(opacity * 255).toString(16).padStart(2, '0')}`;
        ctx.fill();
        
        if (particle.life >= particle.maxLife) {
          particlesRef.current[index] = createParticle();
        }
      });
      
      animationRef.current = requestAnimationFrame(animate);
    };
    
    animate();
    
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [state, audioLevel, getColors]);
  
  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 pointer-events-none"
      style={{ mixBlendMode: 'screen' }}
    />
  );
}