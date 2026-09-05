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

/** Whether a cloud *model* is connected at all.
 *
 *  **Distinct from `canLeaveDevice`, and conflating them says something
 *  false.** This asks whether a route to a cloud model is configured; that
 *  asks whether anything is permitted to leave. They disagree in the ordinary
 *  case of a key pasted with no egress rule yet — measured on this machine,
 *  30 August 2026: `providers` held `openrouter` while `can_leave_device` was
 *  `false`.
 *
 *  Exported because two readers need it — the orb's label and the routing
 *  picker beside the composer — and a second inline copy is how they come to
 *  tell the user different things about one machine. The same argument
 *  `hostOf` settles for a citation's domain.
 */
export function cloudModelConnected(routing: RoutingState | null): boolean {
  return (routing?.providers ?? []).some((p) => p.locality && p.locality !== 'local');
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

/** Whether Zaram can draw a picture on this machine, and what to say if not.
 *
 *  Same argument as speech, one step further. Image generation has **no menu
 *  item** — `CLAUDE.md` keeps tools out of the navigation, so the only way to
 *  ask for a picture is to type one — which means a user has no way at all to
 *  discover whether it works. A capability that is off silently reads as a
 *  broken product; a capability that is *on* silently is one nobody finds.
 *
 *  `reason` and `remedy` come from the backend rather than being composed
 *  here, because it is the thing that knows which of three separate absences
 *  it is looking at — no torch, no diffusers, or no checkpoint — and each has
 *  its own fix and its own download size.
 *
 *  This reports **readiness, never residency**. The model loads on first use,
 *  not at boot: SDXL is ~7 GB and a 27B chat model with its cache is ~10.7 GB,
 *  so on a 12 GB card holding both is not slow, it is impossible. */
export interface ImageAvailability {
  canDraw: boolean;
  /** Why not. Empty when it can. */
  reason: string;
  /** What would fix it, with the size named. Empty when it can. */
  remedy: string;
  /** What would draw — the checkpoint's own name. Empty when nothing would. */
  provider: string;
}

interface SystemState {
  backendOnline: boolean;
  /** Null until the first successful poll — distinct from "known offline". */
  routing: RoutingState | null;
  speech: SpeechAvailability;
  /** Null until the first successful poll, on the same rule as `speech`. */
  images: ImageAvailability | null;
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
  /** Which model is being loaded *and does not fit this machine*, while
   *  `activity` is `warming`. Null otherwise, on the same rule as `swappingTo`.
   *
   *  Its own field rather than a seventh `OrbActivity`, because the orb is
   *  showing the truth already — this is a load, and it is warming. What
   *  differs is the sentence underneath: an ordinary cold start passes and the
   *  session gets fast, while a model larger than the whole VRAM budget has
   *  spilled layers into system RAM and will be slow on *every* reply. Telling
   *  the user "the first reply of a session takes longer" in that case is a
   *  promise the machine cannot keep. */
  oversizedModel: string | null;

  setActivity: (a: OrbActivity) => void;
  /** Enter the swap state, naming the model being loaded, and move the orb with
   *  it. One call sets both stores: they are two renderings of one fact, and
   *  letting a caller set one without the other is how the orb turns
   *  slate-grey while the label still reads "Local only". */
  beginModelSwap: (model: string) => void;
  /** Leave the swap for whatever comes next, clearing the model name. */
  endModelSwap: (next?: OrbActivity) => void;
  /** Enter the warming state for a model the provider layer graded as larger
   *  than the whole resident budget. */
  beginOversizedLoad: (model: string) => void;
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
  images: null,
  activity: 'idle',
  swappingTo: null,
  cloudAnsweredAt: null,
  oversizedModel: null,

  // Clears both model names on every transition, so neither can outlive the
  // state that explains it.
  setActivity: (activity) => set({ activity, swappingTo: null, oversizedModel: null }),

  // Set together, for the reason `beginModelSwap` is: they are two halves of
  // one fact, and a caller that sets the activity without the name produces a
  // warming label that cannot say why this wait is different.
  beginOversizedLoad: (model) =>
    set({ activity: 'warming', swappingTo: null, oversizedModel: model }),

  beginModelSwap: (model) => {
    set({ activity: 'swapping', swappingTo: model });
    useOrbStore.getState().setOrbState('swapping');
  },

  endModelSwap: (next = 'thinking') => {
    set({ activity: next, swappingTo: null, oversizedModel: null });
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
      // Absent means an older backend that does not report it, which is not
      // the same as "cannot draw" — so it stays null and the surface says
      // nothing, rather than claiming a capability is missing on the strength
      // of a field that was never sent.
      const img = data?.images;
      set({
        backendOnline: data?.kernel === 'online',
        speech: connector?.available ? 'available' : 'not-installed',
        images: img
          ? {
              canDraw: Boolean(img.can_draw),
              reason: String(img.reason ?? ''),
              remedy: String(img.remedy ?? ''),
              provider: String(img.provider ?? ''),
            }
          : null,
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
  /** Optional so existing callers keep working; absent reads as "the model
   *  fits", which understates the problem rather than inventing one. */
  oversizedModel?: string | null;
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
    // **A model larger than the whole budget is not an ordinary cold start,
    // and saying it is would be a promise the machine cannot keep.**
    //
    // `ProviderManager.swap_preflight` grades this as `oversized` — "larger
    // than the whole budget, so evicting everything would not help; it will
    // load with layers spilled to system RAM" — and its own docstring says
    // why the verdict is worth having separately: "a cold start passes on its
    // own; an oversized model is a hardware fact no setting will change".
    //
    // The backend has been sending it. `chatClient` dropped it on the floor as
    // an unrecognised kind, so what the user got instead was silence, then a
    // read timeout naming a URL — for a condition the product had graded
    // correctly before generation started.
    if (s.oversizedModel) {
      return {
        label: 'Warming up',
        detail: `${s.oversizedModel} is larger than this machine’s graphics memory, so part of it runs on the processor. It will answer, slowly, and every reply will be slow — a smaller model is the remedy.`,
        tone: 'busy',
      };
    }
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
    // **Read off the thing that answers, never off the machine's posture.**
    //
    // This said `Working remotely.` whenever `routing.mode` was anything but
    // `local` — and `mode` is the overall posture, so connecting a cloud
    // provider made it say so while a local model was generating. Observed on
    // the ambient panel with TabbyAPI answering on loopback: "Thinking.
    // Working remotely." A false claim that the user's question left the
    // machine, on the surface `CLAUDE.md` singles out as the one where the
    // egress disclosure matters most.
    //
    // The fix is the correction `applyHealth` twenty lines up already made for
    // the persistent bar, in its own words: *"mode describes the machine's
    // overall posture and this must describe the thing that actually
    // answers"*. Half the fix landed; this branch was the other half.
    //
    // Unknown says neither, following `locality_of` in `core/identity.py`:
    // "runs on this machine" would be a confident false claim on the one fact
    // a user is most likely to check, and so would its opposite.
    const locality = (s.routing?.providers ?? [])[0]?.locality;
    const where =
      locality === 'local' ? ' on this machine' : locality === 'cloud' ? ' remotely' : '';
    return { label: 'Thinking', detail: `Working${where}.`, tone: 'busy' };
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
  const cloudAvailable = cloudModelConnected(s.routing);

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
