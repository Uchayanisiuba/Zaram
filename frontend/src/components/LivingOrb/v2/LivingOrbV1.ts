import { EnergyRings } from '../EnergyRings';
import { ParticleSystem } from '../ParticleSystem';

export function LivingOrbV1() {
  return (
    <div className="relative w-full h-full">
      <EnergyRings />
      <ParticleSystem />
    </div>
  );
}