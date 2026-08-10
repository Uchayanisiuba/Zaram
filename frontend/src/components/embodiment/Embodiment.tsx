import { Suspense, lazy, useState, type ComponentProps } from 'react'
import LivingOrb from '@/components/orb/LivingOrb'
import { useEmbodimentStore } from '@/stores/embodimentStore'

/**
 * Picks which renderer embodies the system state.
 *
 * `docs/EMBODIMENT-SPIKE.md`: the renderer is chosen **at mount and does not
 * crossfade**. A crossfade between a glowing sphere and a 3D character has no
 * good frame in the middle, and a preference changed in Settings does not need
 * to animate on a surface the user is not looking at. Changing the setting
 * changes what mounts next.
 *
 * That is also what removes the worst version of the bundle problem. `three`
 * plus `@pixiv/three-vrm` is roughly 600 KB–1 MB gzipped. With no crossfade
 * there is never a moment where both renderers are live, so the lazy import
 * below is fetched only by people who turned the avatar on — the orb path never
 * pays for it. The packaging discipline that refused 321 MB for OCR should not
 * quietly accept a megabyte here.
 *
 * `VrmAvatar` does not import from `LivingOrb` and `LivingOrb` does not know
 * this file exists. Both read `useEmbodimentState()` and nothing else.
 */
const VrmAvatar = lazy(() => import('./VrmAvatar'))

type EmbodimentProps = ComponentProps<typeof LivingOrb>

export default function Embodiment(props: EmbodimentProps) {
  // Read once, at mount. Subscribing would re-render into the other renderer
  // the instant the preference changed, which is the crossfade the spike
  // rejected — arriving by accident instead of by design.
  const [renderer] = useState(() => useEmbodimentStore.getState().renderer)

  if (renderer === 'orb') return <LivingOrb {...props} />

  return (
    <Suspense fallback={<LivingOrb {...props} />}>
      <VrmAvatar px={props.px} />
    </Suspense>
  )
}
