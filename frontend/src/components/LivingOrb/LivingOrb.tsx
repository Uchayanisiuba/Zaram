import { OrbEngine } from '../OrbEngine/OrbEngine'

export function LivingOrb() {
  return (
    <div className="relative w-96 h-96 flex items-center justify-center pointer-events-none">
      <OrbEngine className="w-full h-full" />
    </div>
  )
}

export default LivingOrb