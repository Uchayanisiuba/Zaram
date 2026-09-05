/**
 * The wait, while a picture is being drawn.
 *
 * Why this exists at all
 * ----------------------
 * With code you watch it being written, so the delay explains itself. An image
 * is silent for its whole duration: nothing streams, the orb says "working",
 * and thirty seconds pass with the screen unchanged. That is indistinguishable
 * from a hang, and a user who concludes the product hung does not wait for the
 * picture.
 *
 * Percentage and step count, never time remaining
 * -----------------------------------------------
 * A diffusion pipeline emits a callback per denoising step, so the number here
 * is **measured** — it comes off the sampler, one event per step. Seconds-left
 * is not measured; it is an extrapolation from however many steps have run,
 * which is nothing at the moment it would first be shown, and a confident
 * wrong number is worse than no number. The same discipline `vram_bytes` keeps
 * by returning `None` rather than `0`, and `locality_of` by refusing to say
 * "local" for a model it cannot place.
 *
 * The decision was the maintainer's and it is recorded here rather than only
 * in a handoff, so it does not get re-argued the next time somebody notices
 * that other products show an ETA.
 */
import { Loader2 } from 'lucide-react';

import type { ImageProgress } from '@/services/chatClient';

export default function ImageProgressCard({
  progress,
}: {
  progress: ImageProgress | null;
}) {
  if (!progress) return null;

  const batched = progress.count > 1;

  return (
    <div
      className="my-2 rounded-xl px-4 py-3"
      style={{
        border: '1px solid var(--color-border-subtle)',
        background: 'var(--color-glass)',
        maxWidth: 520,
      }}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2">
        <Loader2
          size={13}
          className="animate-spin shrink-0"
          style={{ color: 'var(--color-indigo-light)' }}
        />
        <span className="text-[12px]" style={{ color: 'var(--color-text)' }}>
          {batched
            ? `Drawing image ${progress.index} of ${progress.count}`
            : 'Drawing'}
        </span>
        <div className="flex-1" />
        <span
          className="text-[11px] tabular-nums"
          style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}
        >
          {progress.percent}%
        </span>
      </div>

      {/* The bar. `percent` is written straight to the width because it was
          measured; nothing here smooths, eases or animates towards a target,
          which would put a number on screen that no step reported. */}
      <div
        className="mt-2 h-1 w-full overflow-hidden rounded-full"
        style={{ background: 'var(--color-border-subtle)' }}
      >
        <div
          className="h-full rounded-full"
          style={{
            width: `${progress.percent}%`,
            background: 'var(--color-indigo-light)',
            transition: 'width 120ms linear',
          }}
        />
      </div>

      {/* The step count under the bar, because it is the honest unit. A
          percentage is a rendering of it, and when the two are shown together
          a reader can see that the number is counting something real. */}
      <div
        className="mt-1.5 text-[11px]"
        style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}
      >
        step {progress.step} of {progress.total_steps}
      </div>
    </div>
  );
}
