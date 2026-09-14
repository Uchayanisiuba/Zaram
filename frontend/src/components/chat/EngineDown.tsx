/**
 * The engine is not running: one sentence, once, with the remedy.
 *
 * Before this, an unreachable backend produced four fragments on one screen
 * — *Offline* under the orb, *list unavailable* twice in the footer,
 * *Routing unavailable*, and *Speech recognition is unavailable (500)* under
 * the composer — each true, each written by a component that could not know
 * the others existed, and together reading as five things broken rather than
 * one thing not running. `docs/RUNNING.md` already names the failure in a
 * sentence. This is that sentence, in the conversation, in place of the
 * fragments; the components that wrote them stay quiet while it stands
 * (`ChatSurface` withholds them on `backendOnline === false`).
 *
 * It does not guess at a cause. The four ways the engine fails to start in
 * `RUNNING.md` are a developer's traps — a held port, a stale checkout, a
 * second virtualenv — and naming one to a person who installed Zaram would be
 * a confident wrong diagnosis. What every case shares is the remedy: start it
 * again. Nothing is invented and nothing polls harder — the same /health poll
 * that reports it down will report it back.
 */
import { CircleAlert } from 'lucide-react';

export default function EngineDown() {
  return (
    <div
      role="alert"
      className="surface rounded-xl px-4 py-3 flex items-start gap-3"
      data-testid="engine-down"
    >
      <CircleAlert size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--color-red)' }} aria-hidden />
      <div className="flex flex-col gap-1">
        <p className="t-body" style={{ margin: 0 }}>
          Zaram’s engine is not running, so nothing can be answered right now.
        </p>
        <p className="text-xs" style={{ margin: 0, color: 'var(--color-text-muted)' }}>
          Quit and reopen Zaram. This screen returns to normal on its own once the engine is back.
        </p>
      </div>
    </div>
  );
}
