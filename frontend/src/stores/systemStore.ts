/**
 * System state — what the Orb reports.
 *
 * CLAUDE.md: "The Orb shows system state (idle / thinking / routing to cloud /
 * local only). It does not perform."
 *
 * This is the product claim made continuously visible. Everything here comes
 * from the backend; nothing is inferred or assumed. If a field can only say one
 * thing today, it says one thing today — a fabricated signal in a privacy
 * indicator is worse than no indicator, because it would be trusted.
 */
import { create } from 'zustand';

import { useOrbStore } from './orbStore';
import { useSessionStatusStore } from './sessionStatusStore';

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** What the Orb is currently doing or reporting.
 *
 *  `warming` and `swapping` are different waits and are told apart deliberately.
 *  Warming is a cold start — nothing was resident and the first model is being
 *  loaded. Swapping is an *eviction*: a model that was answering has to be
 *  unloaded to make room for the one this request routed to. CLAUDE.md requires
 *  the second to be visible ("a route that requires a swap must be visible in
 *  the orb's state"), and it needs its own word because the remedy differs —
 *  warming passes on its own, while a swap recurring every other message is a
 *  model-assignment problem the user can fix in Settings. */
export type OrbActivity = 'idle' | 'warming' | 'thinking' | 'speaking' | 'listening' | 'swapping';

/** Where work is being routed. Today always 'local' — only Ollama is wired. */
export type RoutingMode = 'local' | 'cloud' | 'mixed' | 'unknown';

export interface RoutingState {
  mode: RoutingMode;
  providers: { id: string; locality: string; model?: string | null }[];
  webSearch: 'enabled' | 'disabled' | 'unknown';
  /** Whether any route off this machine exists at all. */
  canLeaveDevice: boolean;
}

/** Whether speech synthesis can actually run.
 *
 *  Voice ships as an optional extra — Kokoro pulls torch, transformers and the
 *  spaCy stack, roughly 830 MB — so "unavailable" is the expected state on a
 *  base install rather than a fault. It still has to be *said*: a control that
 *  is greyed out with no explanation is the silent-failure pattern, and the
 *  user has no way to know whether it is broken, unfinished, or simply not
 *  installed. Null means the backend has not reported yet. */
export type SpeechAvailability = 'available' | 'not-installed' | null;

interface SystemState {
  backendOnline: boolean;
  /** Null until the first successful poll — distinct from "known offline". */
  routing: RoutingState | null;
  speech: SpeechAvailability;
  activity: OrbActivity;
  /** Which model is being loaded, while `activity` is `swapping`.
   *
   *  Null in every other state. A stale model name under an idle orb would be
   *  an invented value, and this file's own rule is that a fabricated signal is
   *  worse than no signal because it would be trusted. */
  swappingTo: string | null;
  /** When a cloud model last actually answered, or null if none has.
   *
   *  **The difference between this and `routing.providers` is the whole point
   *  of the indicator.** A connected provider is a *capability* — something
   *  that could answer. This is an *event* — something that did, observed from
   *  the backend's `answering` report, which is resolved from the routing that
   *  really happened rather than from what is configured.
   *
   *  It replaces `lastEgressAt`, which was declared with a `noteEgress` action
   *  beside it and never called by anything: a signal that could only ever read
   *  null, on the one indicator that must not be decorative. */
  cloudAnsweredAt: number | null;

  setActivity: (a: OrbActivity) => void;
  /** Enter the swap state, naming the model being loaded, and move the orb with
   *  it. One call sets both stores: they are two renderings of one fact, and
   *  letting a caller set one without the other is how the orb turns
   *  slate-grey while the label still reads "Local only". */
  beginModelSwap: (model: string) => void;
  /** Leave the swap for whatever comes next, clearing the model name. */
  endModelSwap: (next?: OrbActivity) => void;
  /** Record that a cloud model answered. Called from the chat stream when the
   *  backend reports `locality: 'cloud'` — an observation, never a setting. */
  noteCloudAnswer: () => void;
  refresh: () => Promise<void>;
  startPolling: (intervalMs?: number) => () => void;
}

export const useSystemStore = create<SystemState>((set, get) => ({
  backendOnline: false,
  routing: null,
  speech: null,
  activity: 'idle',
  swappingTo: null,
  cloudAnsweredAt: null,

  // Clears `swappingTo` on every transition, so the name cannot outlive the
  // state that explains it.
  setActivity: (activity) => set({ activity, swappingTo: null }),

  beginModelSwap: (model) => {
    set({ activity: 'swapping', swappingTo: model });
    useOrbStore.getState().setOrbState('swapping');
  },

  endModelSwap: (next = 'thinking') => {
    set({ activity: next, swappingTo: null });
    // `listening` and `swapping` are the only OrbActivity members the orb has
    // no visual for, and neither can follow a swap — so this mapping is total
    // in practice without a cast that would hide a future gap.
    useOrbStore.getState().setOrbState(next === 'warming' ? 'thinking' : next);
  },

  noteCloudAnswer: () => set({ cloudAnsweredAt: Date.now() }),

  refresh: async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (!res.ok) {
        set({ backendOnline: false });
        return;
      }
      const data = await res.json();
      const r = data?.routing ?? {};
      const providers = Array.isArray(r.providers) ? r.providers : [];
      // The active connector reports whether it could import Kokoro at all.
      // Absent or unavailable means the voice extra is not installed, which is
      // the ordinary state of a base install and must be explained rather than
      // shown as a dead control.
      const connector = data?.speech?.active_connector_health;
      set({
        backendOnline: data?.kernel === 'online',
        speech: connector?.available ? 'available' : 'not-installed',
        routing: {
          mode: (r.mode as RoutingMode) ?? 'unknown',
          providers,
          webSearch: r.web_search ?? 'unknown',
          canLeaveDevice: Boolean(r.can_leave_device),
        },
      });

      // The persistent bar needs the model and where it runs. Taken from the
      // inference provider rather than from routing.mode, because mode
      // describes the machine's overall posture and this must describe the
      // thing that actually answers. Null when the backend does not name one.
      const inference = providers[0];
      useSessionStatusStore.getState().applyHealth({
        model: inference?.model ?? null,
        locality: inference?.locality === 'local' ? 'local' : inference?.locality ? 'cloud' : null,
      });
    } catch {
      // Unreachable is a real state and must be shown, not hidden behind the
      // last known good value.
      set({ backendOnline: false });
    }
  },

  startPolling: (intervalMs = 10_000) => {
    void get().refresh();
    const id = setInterval(() => void get().refresh(), intervalMs);
    return () => clearInterval(id);
  },
}));

/** One line describing the system, in plain language. Shown on the Orb.
 *  CLAUDE.md: show routing decisions in plain language; never claim absolute
 *  security — state what is verifiable. */
export function describeSystem(s: {
  backendOnline: boolean;
  routing: RoutingState | null;
  activity: OrbActivity;
  swappingTo?: string | null;
  /** When a cloud model actually answered. Optional so existing callers keep
   *  working, and absent reads as "none has", which is the safe direction:
   *  a caller that forgets to pass it understates egress rather than
   *  inventing it. */
  cloudAnsweredAt?: number | null;
}): { label: string; detail: string; tone: 'local' | 'cloud' | 'offline' | 'busy' } {
  if (!s.backendOnline) {
    return {
      label: 'Offline',
      detail: 'Zaram’s engine is not running, so nothing can be answered.',
      tone: 'offline',
    };
  }
  if (s.activity === 'swapping') {
    // CLAUDE.md: "a route that requires a swap must be visible in the orb's
    // state. An invisible swap reads as a broken product." The orb shows it;
    // this says why, because a dimmed orb alone tells the user something is
    // happening without telling them it will end.
    //
    // The model is named when known. It is the one detail that turns an
    // unexplained wait into a comprehensible one, and it is also the evidence
    // a user needs to go and change the assignment in Settings if this keeps
    // happening.
    return {
      label: 'Switching model',
      detail: s.swappingTo
        ? `Loading ${s.swappingTo}. It has to replace the model already in memory, which takes a few seconds.`
        : 'Loading a different model. It has to replace the one already in memory, which takes a few seconds.',
      tone: 'busy',
    };
  }
  if (s.activity === 'warming') {
    // Said only after a request has gone several seconds with no output, which
    // on a local model means it is still being loaded into memory. Without
    // this the first message of a session looks like a hang.
    return {
      label: 'Warming up',
      detail: 'Starting the local model. The first reply of a session takes longer.',
      tone: 'busy',
    };
  }
  if (s.activity === 'thinking') {
    const where = s.routing?.mode === 'local' ? 'on this machine' : 'remotely';
    return { label: 'Thinking', detail: `Working ${where}.`, tone: 'busy' };
  }
  // **Capability is not activity, and the colour must track activity.**
  //
  // An earlier fix split these two claims apart in *words* — "Cloud enabled"
  // against "Local · can send" — and left both of them returning `tone:
  // 'cloud'`, which `OrbStatusLabel` paints amber, the same colour this
  // product uses for a warning. So connecting a provider, or allowing one
  // search host, lit a standing amber warning that never went out, while every
  // answer was still being generated on the machine. Half the fix: the labels
  // were corrected and the signal a user actually reads at a glance was not.
  //
  // Colour now follows what *happened*. Words carry what is *possible*, since
  // a capability is worth stating and is not worth alarming about.
  if (s.cloudAnsweredAt) {
    return {
      label: 'Cloud used',
      detail: 'A cloud model answered in this session. Activity shows what left.',
      tone: 'cloud',
    };
  }

  // Observed from `routing.providers`, which is configuration: these two say a
  // route *exists*, never that anything took it.
  const cloudAvailable = (s.routing?.providers ?? []).some(
    (p) => p.locality && p.locality !== 'local',
  );

  if (cloudAvailable) {
    return {
      label: 'Local · cloud ready',
      detail:
        'Answers are running on this machine. A cloud model is connected, and Zaram names it before it answers.',
      tone: 'local',
    };
  }
  if (s.routing?.canLeaveDevice) {
    return {
      label: 'Local · can send',
      detail:
        'Answers are generated on this machine. Something else is allowed to send — see Activity.',
      tone: 'local',
    };
  }
  return {
    label: 'Local only',
    detail: 'Inference runs on this machine and nothing is sent out.',
    tone: 'local',
  };
}
