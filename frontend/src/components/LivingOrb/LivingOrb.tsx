// src/components/LivingOrb/LivingOrb.tsx
import { FEATURES } from '../../config/features';
import { LivingOrbV1 } from './v1/LivingOrbV1';
// import { LivingOrbV2 } from './v2/LivingOrbV2'; // Will be enabled in Phase 2

export function LivingOrb() {
  // Strangler Fig Pattern: Route to the new renderer when the flag is active
  if (FEATURES.USE_ORB_RENDERER_V2) {
    // return <LivingOrbV2 />; 
    return <div>Orb v2.0 is active but not yet implemented.</div>;
  }

  // Default to the stable, working v1 implementation
  return <LivingOrbV1 />;
}