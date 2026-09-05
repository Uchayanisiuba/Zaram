/**
 * The download itself: what it is doing, how far it has got, and what to do
 * when it stops.
 *
 * `FirstRunPanel` has shown a greyed "download a model" offer since it was
 * built, with its own line saying Zaram cannot set it up for you yet. This is
 * the executor that lets that line come off, and it is the second one to
 * arrive — `CloudKeyForm` was the first, and for the same reason: the backend
 * behind it exists and is effective without a restart.
 *
 * Three rules, each easy to lose by making the screen friendlier.
 *
 * **The percentage is the pull's own arithmetic, not the manifest's.** The
 * offer quoted an approximate size from a dated list; the stream reports the
 * real total. Counting progress against the quoted figure would produce a bar
 * that reaches 103% or stalls at 96%, and a progress bar that lies about the
 * end is worse than no bar — the user cannot tell it from a stall.
 *
 * **No model filename, here either.** The stage line is written by the
 * backend in a person's words. Nothing on this screen composes one.
 *
 * **A failure says what happened and leaves the button.** A download that
 * dies at 80% on a metered connection is the worst moment in this product to
 * be vague, and the one thing the user needs is the option to try again.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { pullRecommendedModel, type PullEvent } from '@/services/pullClient';

interface ModelPullProps {
  /** The model can now answer, so readiness should be asked again. */
  onFinished: () => void;
}

type Phase =
  | { status: 'idle' }
  | { status: 'running'; stage: string; completed: number; total: number }
  | { status: 'failed'; message: string };

export default function ModelPull({ onFinished }: ModelPullProps) {
  const [phase, setPhase] = useState<Phase>({ status: 'idle' });
  // Kept in a ref as well as in state: the reader loop runs outside React and
  // must not resurrect a component that has already unmounted.
  const live = useRef(true);
  useEffect(() => () => {
    live.current = false;
  }, []);

  const start = useCallback(() => {
    setPhase({ status: 'running', stage: 'Starting', completed: 0, total: 0 });

    const onEvent = (event: PullEvent) => {
      if (!live.current) return;
      if (event.error) {
        setPhase({ status: 'failed', message: event.error });
        return;
      }
      if (event.done) {
        onFinished();
        return;
      }
      setPhase((current) => ({
        status: 'running',
        stage: event.stage ?? (current.status === 'running' ? current.stage : 'Working'),
        completed: event.completed ?? (current.status === 'running' ? current.completed : 0),
        total: event.total ?? (current.status === 'running' ? current.total : 0),
      }));
    };

    pullRecommendedModel(onEvent).catch((error: unknown) => {
      if (!live.current) return;
      setPhase({
        status: 'failed',
        message: error instanceof Error ? error.message : 'the download stopped',
      });
    });
  }, [onFinished]);

  if (phase.status === 'running') {
    const percent = phase.total > 0 ? Math.floor((phase.completed / phase.total) * 100) : null;
    return (
      <div className="flex flex-col gap-1.5" data-testid="model-pull">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-xs" style={{ color: 'var(--color-text)' }}>
            {phase.stage}
          </span>
          {/* Only once there is a real total to count against. Before that
              there is no percentage, and inventing one would be a number the
              user watches instead of the truth. */}
          {percent !== null && (
            <span
              className="text-[11px]"
              style={{
                color: 'var(--color-text-muted)',
                fontFamily: 'var(--font-mono, ui-monospace, monospace)',
              }}
            >
              {percent}%
            </span>
          )}
        </div>
        <div
          className="h-1 rounded-full overflow-hidden"
          style={{ background: 'rgba(255,255,255,0.08)' }}
          role="progressbar"
          aria-valuenow={percent ?? undefined}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Downloading a model"
        >
          <div
            className="h-full transition-[width] duration-300"
            style={{
              width: percent === null ? '15%' : `${percent}%`,
              background: 'var(--color-cyan-light)',
              opacity: percent === null ? 0.4 : 1,
            }}
          />
        </div>
        <p className="text-[11px] leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
          You can keep using everything else while this runs.
        </p>
      </div>
    );
  }

  if (phase.status === 'failed') {
    return (
      <div className="flex flex-col gap-2" data-testid="model-pull">
        <p className="text-xs leading-relaxed" style={{ color: 'var(--color-text)' }}>
          The download stopped: {phase.message}
        </p>
        <TryAgain onClick={start} label="Try again" />
      </div>
    );
  }

  return (
    <div data-testid="model-pull">
      <TryAgain onClick={start} label="Start the download" />
    </div>
  );
}

function TryAgain({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="self-start rounded-lg border px-2.5 py-1.5 text-xs"
      style={{
        borderColor: 'var(--color-cyan-light)',
        background: 'rgba(125,211,252,0.08)',
        color: 'var(--color-text)',
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );
}
