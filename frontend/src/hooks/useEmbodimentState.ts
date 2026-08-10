import { useOrbStore } from '@/stores/orbStore';
import { useSessionStatusStore } from '@/stores/sessionStatusStore';

/**
 * The one state both embodiment renderers read.
 *
 * `docs/EMBODIMENT-SPIKE.md` calls this the seam, and it exists for a specific
 * reason: activity and locality live in two stores *on purpose*. `orbStore`
 * holds what the system is doing; `sessionStatusStore` holds where the answer
 * came from. They change at different rates for different reasons, and
 * collapsing them was rejected once already — a /health poll would clobber the
 * recall count of a reply in flight.
 *
 * So neither store grows a field duplicating the other. The embodiment state is
 * *derived* from both, here, once. That is what stops a VRM adapter reaching
 * into three stores and slowly acquiring opinions about routing.
 *
 * The spike is explicit about what must not happen: the VRM adapter must not
 * import from `LivingOrb`, and `LivingOrb` must not learn another renderer
 * exists. Both read this hook and nothing else.
 */
export type EmbodimentState =
  | 'idle'
  | 'thinking'
  | 'speaking'
  | 'listening'
  | 'local'
  | 'cloud'
  | 'swapping';

/**
 * Activity wins over locality whenever there is any.
 *
 * Locality only surfaces at rest. "Thinking on a cloud model" is one state to a
 * viewer, not two, and an avatar cannot show both without inventing a vocabulary
 * the user has to learn. At rest there is nothing else to say, so *where the
 * last answer came from* is the useful thing to show — and it is the product's
 * whole claim rendered as a resting expression.
 *
 * When locality is unknown the answer is `idle`, never a guess. CLAUDE.md:
 * never render invented values. An avatar that looks "local" because local is
 * likely would be believed.
 */
export function useEmbodimentState(): EmbodimentState {
  const orbState = useOrbStore((s) => s.orbState);
  const locality = useSessionStatusStore((s) => s.locality);

  if (orbState !== 'idle') return orbState;
  if (locality === 'local') return 'local';
  if (locality === 'cloud') return 'cloud';
  return 'idle';
}
