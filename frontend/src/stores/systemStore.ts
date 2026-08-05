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

import { useSessionStatusStore } from './sessionStatusStore';

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** What the Orb is currently doing or reporting. */
export type OrbActivity = 'idle' | 'warming' | 'thinking' | 'speaking' | 'listening';

/** Where work is being routed. Today always 'local' — only Ollama is wired. */
export type RoutingMode = 'local' | 'cloud' | 'mixed' | 'unknown';

export interface RoutingState {
  mode: RoutingMode;
  providers: { id: string; locality: string; model?: string | null }[];
  webSearch: 'enabled' | 'disabled' | 'unknown';
  /** Whether any route off this machine exists at all. */
  canLeaveDevice: boolean;
}

interface SystemState {
  backendOnline: boolean;
  /** Null until the first successful poll — distinct from "known offline". */
  routing: RoutingState | null;
  activity: OrbActivity;
  /** Timestamp of the last confirmed egress, for the Orb's pulse. Nothing can
   *  leave today, so this stays null until web search is governed and enabled. */
  lastEgressAt: number | null;

  setActivity: (a: OrbActivity) => void;
  noteEgress: () => void;
  refresh: () => Promise<void>;
  startPolling: (intervalMs?: number) => () => void;
}

export const useSystemStore = create<SystemState>((set, get) => ({
  backendOnline: false,
  routing: null,
  activity: 'idle',
  lastEgressAt: null,

  setActivity: (activity) => set({ activity }),
  noteEgress: () => set({ lastEgressAt: Date.now() }),

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
      set({
        backendOnline: data?.kernel === 'online',
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
}): { label: string; detail: string; tone: 'local' | 'cloud' | 'offline' | 'busy' } {
  if (!s.backendOnline) {
    return {
      label: 'Offline',
      detail: 'Zaram’s engine is not running, so nothing can be answered.',
      tone: 'offline',
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
  // Two different claims, previously collapsed into one. "Cloud enabled" says
  // a cloud model is answering your questions. `canLeaveDevice` only says some
  // route off the machine exists — allowing a single search host used to flip
  // the Orb to "Cloud enabled" while every answer was still generated locally.
  // On the one indicator whose entire job is to be trusted, that is the worst
  // thing to be wrong about.
  const cloudInference = (s.routing?.providers ?? []).some(
    (p) => p.locality && p.locality !== 'local',
  );

  if (cloudInference) {
    return {
      label: 'Cloud enabled',
      detail: 'A cloud model can answer your questions. Check Activity for what left.',
      tone: 'cloud',
    };
  }
  if (s.routing?.canLeaveDevice) {
    return {
      label: 'Local · can send',
      detail:
        'Answers are generated on this machine. Something else is allowed to send — see Activity.',
      tone: 'cloud',
    };
  }
  return {
    label: 'Local only',
    detail: 'Inference runs on this machine and nothing is sent out.',
    tone: 'local',
  };
}
