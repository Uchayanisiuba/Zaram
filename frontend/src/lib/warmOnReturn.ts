/**
 * Reload the local model when the person comes back, not when they press Enter.
 *
 * `docs/PLAN.md` A4. The backend keeps the weights resident for thirty
 * minutes after the last request; a longer pause unloads them, and on a SATA
 * SSD the next question then waits twenty seconds for a reload before its
 * first token — the "slow sometimes" that is really "slow after lunch". The
 * window regaining focus after such a pause is the earliest moment we know
 * the person is back and the latest moment the reload is still free: they
 * are reading, not waiting.
 *
 * **Every refusal the backend applies still applies.** `POST /models/warm`
 * goes through `warm_local_model`, which declines when nothing is selected,
 * under `prefer_cloud`, and when the model does not fit what the card has
 * free *now* — so a person returning from Unreal with the card full is not
 * handed a load they did not ask for. This module only decides *when to
 * ask*; the answer is the backend's.
 *
 * It asks once per return, and only after a pause long enough to matter.
 * Focus events fire on every alt-tab, and warming on each would be a request
 * per glance.
 */
import { useChatStore } from '@/stores/chatStore';

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** A pause shorter than this leaves the model resident (`KEEP_ALIVE` is 30
 *  minutes); asking again would load nothing. Slightly under, because the
 *  clock that matters is the server's and started at its last request. */
export const IDLE_BEFORE_WARM_MS = 25 * 60 * 1000;

export interface WarmClock {
  now(): number;
}

/** Wire the focus listener. Returns the teardown. */
export function installWarmOnReturn(
  clock: WarmClock = { now: () => Date.now() },
  post: (path: string) => Promise<unknown> = (path) =>
    fetch(`${API_BASE}${path}`, { method: 'POST', headers: { 'X-Zaram-Client': 'zaram-ui' } }),
): () => void {
  let lastRequestAt = clock.now();
  let asking = false;

  // A reply in flight is a request the server just saw; its end is the
  // moment the thirty minutes start.
  const unsubscribe = useChatStore.subscribe((state, previous) => {
    if (state.isStreaming !== previous.isStreaming) lastRequestAt = clock.now();
  });

  const onReturn = () => {
    if (document.visibilityState === 'hidden') return;
    if (asking) return;
    if (clock.now() - lastRequestAt < IDLE_BEFORE_WARM_MS) return;
    asking = true;
    // Counted as a request whether or not the server loaded anything: a
    // refusal is an answer, and asking again on the next alt-tab would not
    // change it.
    lastRequestAt = clock.now();
    void post('/models/warm')
      .catch(() => undefined)
      .finally(() => {
        asking = false;
      });
  };

  window.addEventListener('focus', onReturn);
  document.addEventListener('visibilitychange', onReturn);
  return () => {
    unsubscribe();
    window.removeEventListener('focus', onReturn);
    document.removeEventListener('visibilitychange', onReturn);
  };
}
