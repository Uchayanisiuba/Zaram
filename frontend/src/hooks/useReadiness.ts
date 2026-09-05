/**
 * Asking whether Zaram can answer, and deciding what to do about not knowing.
 *
 * The gate below is the part worth reading. Three states, and only one of them
 * replaces the composer:
 *
 * * **checking** — the answer has not arrived. Show the composer. A first-run
 *   screen that flashes up for 200ms on every open is worse than one that
 *   arrives a moment late.
 * * **unavailable** — the backend could not be asked. Show the composer. A
 *   failed probe says nothing about whether a model is installed, and rendering
 *   "you have no model" because a fetch failed would be an invented value on the
 *   one screen a new user judges the product by. The orb already reports a dead
 *   backend; that is its story, not this component's.
 * * **known** — believe it. `can_chat: false` replaces the composer with the
 *   offers; `true` leaves it alone.
 *
 * Fail toward the working product, in other words: doubt renders chat.
 */
import { useCallback, useEffect, useState } from 'react';

import { fetchReadiness, type ReadinessReport } from '@/services/readinessClient';

export type ReadinessProbe =
  | { status: 'checking' }
  | { status: 'unavailable' }
  | { status: 'known'; report: ReadinessReport };

/**
 * The report to offer instead of a composer, or null to leave the composer be.
 *
 * Pure and exported so the rule above is testable without a component: the
 * three states differ only in what they *do not* claim, which is precisely the
 * kind of thing that gets simplified away by someone reading the happy path.
 */
export function setupToOffer(probe: ReadinessProbe): ReadinessReport | null {
  if (probe.status !== 'known') return null;
  return probe.report.canChat ? null : probe.report;
}

/**
 * Ask once per mount, and again when something has plainly changed.
 *
 * Mounted with the conversation, so this re-asks each time it is opened — which
 * is what makes the screen disappear by itself after someone sets a model up,
 * with nothing to dismiss and nothing remembering a decision. Rule 7e: measure
 * what happened rather than asking the user to predict it.
 *
 * **`recheck` is the same measurement, not a second source of truth**, and it
 * exists because one action on the setup screen can now change the answer
 * without a remount: saving a cloud key takes effect immediately on the
 * backend, so the screen offering it would otherwise keep standing over a
 * product that had just become able to answer. Nothing here caches or infers —
 * the same probe runs again and the backend decides, which is what keeps this
 * from becoming a second opinion that can drift from `/readiness`.
 *
 * Loopback only. `/readiness` reports and never fetches, so asking it costs
 * nothing and consents to nothing.
 */
export function useReadiness(
  probe: () => Promise<ReadinessReport> = fetchReadiness,
): [ReadinessProbe, () => void] {
  const [state, setState] = useState<ReadinessProbe>({ status: 'checking' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    probe()
      .then((report) => {
        if (live) setState({ status: 'known', report });
      })
      .catch(() => {
        if (live) setState({ status: 'unavailable' });
      });
    return () => {
      live = false;
    };
  }, [probe, attempt]);

  const recheck = useCallback(() => setAttempt((n) => n + 1), []);

  return [state, recheck];
}
