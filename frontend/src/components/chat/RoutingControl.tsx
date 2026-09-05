/**
 * Where questions may go, and which model answers — one chip, beside the input.
 *
 * **The friction this removes.** Both decisions used to live in Settings, so
 * keeping the next question on this machine, or sending one to a different
 * model, cost a trip out of the conversation, a scroll, and a trip back. On a
 * product whose thesis is *proximity beats capability*, that is the worst
 * place in the interface to put a control people actually touch.
 *
 * **Why one chip and not three dropdowns.** The row under the composer already
 * carries project and domain. Five controls is clutter, and it would leave
 * model filenames sitting on a resting surface, which `CLAUDE.md` keeps out of
 * the primary path on the grounds that the target user is not technical. So
 * the resting state is plain language, and the names appear only after a
 * deliberate press — where naming them is *required* rather than forbidden,
 * because "never hide the model" is the other half of the same rule.
 *
 * **Local and cloud are separate lists on purpose.** They are different
 * decisions with different stakes: choosing between local models is a speed
 * and quality question, and choosing a cloud model is a question about where a
 * document goes and who trains on it. A single merged list makes those look
 * like one kind of choice, and the second deserves its own heading and its own
 * data-policy line against every entry.
 *
 * **Every installed chat model is listed, including ones Zaram would not pick
 * itself.** `selectable_by_default` gates *auto-routing* — it stops Zaram
 * sending a user's work to a free tier that trains on it without being asked.
 * It is not a gate on the user asking. Filtering those out here would hide a
 * model someone deliberately installed and leave them no explanation, which is
 * the silent-failure pattern; naming the deal beside it is what `CLAUDE.md`
 * asks for instead.
 *
 * Embedders are excluded on `category`, never on a name heuristic: Ollama
 * answers `/api/generate` for `bge-m3` with a 400, so offering it is offering
 * a choice that can only fail.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Cloud, HardDrive, RefreshCw, Shuffle } from 'lucide-react';

import { describeDataPolicy } from '@/components/settings/AdvancedModelField';
import {
  fetchModels,
  fetchRoutingSettings,
  rescanModels,
  updateRoutingSettings,
  type DiscoveredModel,
  type RoutingPreference,
} from '@/services/settingsClient';
import { cloudModelConnected, useSystemStore } from '@/stores/systemStore';

/** The same three words Settings uses.
 *
 *  Not a second vocabulary for one setting: a user should not have to work out
 *  that "Local only" here and "Prefer local" there are the same choice. */
const MODES: { value: RoutingPreference; label: string }[] = [
  { value: 'prefer_local', label: 'Prefer local' },
  { value: 'auto', label: 'Auto' },
  { value: 'prefer_cloud', label: 'Prefer cloud' },
];

const MODE_ICON: Record<RoutingPreference, typeof Cloud> = {
  prefer_local: HardDrive,
  auto: Shuffle,
  prefer_cloud: Cloud,
};

/** Decimal, because that is how a size is quoted everywhere a person will
 *  compare it — a provider's page, a data plan, a disk. */
function gb(bytes: number | null): string {
  if (!bytes) return '';
  return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
}

/** Why this model would be slow, in a sentence with the numbers in it.
 *
 *  "Does not fit" is a verdict a person can only accept. "18.2 GB against
 *  9.1 GB of VRAM" is one they can act on — the same argument
 *  `residentBudgetBytes` was carried across for. */
export function slowNote(model: DiscoveredModel): string | null {
  if (model.fitsResident !== false) return null;
  // Weights plus the model's own cache — the quantity `fitsResident` is
  // decided on. See `describeFit` in SettingsWorkspace for why quoting the
  // on-disk size here can contradict the verdict beside it.
  const claimed = gb(model.residentCostBytes ?? model.sizeBytes);
  const budget = gb(model.residentBudgetBytes);
  if (claimed && budget) return `slow — ${claimed} against ${budget} of VRAM`;
  return 'slow — larger than this machine can hold';
}

export default function RoutingControl() {
  const hasCloudModel = useSystemStore((s) => cloudModelConnected(s.routing));
  const canLeaveDevice = useSystemStore((s) => s.routing?.canLeaveDevice ?? false);
  const cloudUsable = hasCloudModel && canLeaveDevice;

  const [open, setOpen] = useState(false);
  const [preference, setPreference] = useState<RoutingPreference | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const [models, setModels] = useState<DiscoveredModel[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [rescanning, setRescanning] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const settings = await fetchRoutingSettings();
        if (cancelled) return;
        setPreference(settings.routingPreference);
        setPinned(settings.defaultModel);
      } catch {
        // A preference we could not read is not `auto`. Rendering a default
        // never fetched would put an invented value on the control that says
        // where a user's questions go.
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Escape and outside-click, because a panel closable only by the control
  // that opened it is a trap on a surface this small.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      // Captured and stopped, because Escape means "close the thing on top"
      // and the conversation panel is listening for it too. Without this,
      // dismissing this popover closed the whole conversation behind it —
      // measured in the browser, and invisible to a test that renders this
      // component on its own.
      e.stopPropagation();
      setOpen(false);
    };
    const onDown = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey, true);
    document.addEventListener('mousedown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      document.removeEventListener('mousedown', onDown);
    };
  }, [open]);

  /** Fetched on the press, never on render.
   *
   *  `fetchModels` asks every connected cloud provider what it offers, so it
   *  is egress — `settingsClient` says outright that this is why the interface
   *  asks for it "on a button rather than on mount". This control renders on
   *  every conversation; discovery must not ride along with it. */
  const reveal = useCallback(async () => {
    setOpen((was) => !was);
    if (models || loading) return;
    setLoading(true);
    try {
      setModels(await fetchModels());
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [models, loading]);

  /** Look again, because a server may have started since Zaram did.
   *
   *  **This is the fix for the defect that made the whole control look
   *  broken.** Discovery ran once per backend process, so an inference server
   *  started after Zaram was invisible until Zaram was restarted — and from
   *  the outside that is indistinguishable from Zaram having lost a model the
   *  user knows they installed. It sits here rather than only in Settings
   *  because this is the moment of doubt: the list is open and the model is
   *  not in it. */
  async function rescan() {
    setRescanning(true);
    setFailed(false);
    try {
      setModels(await rescanModels());
    } catch {
      setFailed(true);
    } finally {
      setRescanning(false);
    }
  }

  async function save(update: {
    routingPreference?: RoutingPreference;
    defaultModel?: string;
  }) {
    const previous = { preference, pinned };
    if (update.routingPreference) setPreference(update.routingPreference);
    if (update.defaultModel !== undefined) setPinned(update.defaultModel || null);
    setBusy(true);
    setFailed(false);
    try {
      const saved = await updateRoutingSettings(update);
      setPreference(saved.routingPreference);
      setPinned(saved.defaultModel);
    } catch {
      // Put it back. A control that appears to have worked and did not would
      // leave someone believing their next question stays on this machine
      // when it may not.
      setPreference(previous.preference);
      setPinned(previous.pinned);
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  const chats = (models ?? []).filter((m) => m.category === 'llm');
  const local = chats.filter((m) => m.locality === 'local');
  const cloud = chats.filter((m) => m.locality !== 'local');

  const Icon = preference ? MODE_ICON[preference] : Shuffle;
  const modeLabel = MODES.find((m) => m.value === preference)?.label ?? '';

  if (preference === null) {
    return (
      <span className="flex items-center gap-1.5 text-[11px] text-slate-600">
        <Shuffle size={12} aria-hidden className="shrink-0" />
        {failed ? 'Routing unavailable' : 'Checking routing…'}
      </span>
    );
  }

  return (
    <div ref={root} className="relative flex items-center gap-1.5 text-[11px]">
      <button
        type="button"
        onClick={() => void reveal()}
        aria-expanded={open}
        aria-haspopup="dialog"
        data-testid="routing-chip"
        className="flex items-center gap-1.5 text-slate-500 hover:text-slate-300 transition-colors"
      >
        <Icon size={12} aria-hidden className="shrink-0" />
        <span>{modeLabel}</span>
        {/* The user's own pin, named. "Never hide the model" outranks keeping
            filenames off the primary path when the name is the user's own
            deliberate choice — hiding it would make the control lie about what
            is about to answer. */}
        {pinned && <span className="text-slate-600">· {pinned}</span>}
      </button>
      {preference === 'prefer_local' && !pinned && (
        // The guarantee, and only where there is one. `prefer_local` removes
        // cloud models from the candidate set outright; `prefer_cloud` is a
        // bias the consent gate still governs, and claiming symmetry would
        // overstate one half and understate the other.
        <span className="text-slate-600">· stays on this machine</span>
      )}
      {failed && (
        <span className="text-slate-600" title="The change did not save">
          · not saved
        </span>
      )}

      {open && (
        <div
          role="dialog"
          aria-label="Routing and model"
          data-testid="routing-panel"
          className="absolute bottom-full left-0 mb-2 z-50 w-[19rem] max-h-[22rem] overflow-y-auto rounded-lg p-3"
          style={{
            background: 'var(--color-surface, #14161c)',
            border: '1px solid rgba(255,255,255,0.08)',
            boxShadow: '0 12px 32px rgba(0,0,0,0.45)',
          }}
        >
          <p className="text-[10px] uppercase tracking-wide text-slate-500 mb-1.5">
            Where questions may go
          </p>
          <div className="flex gap-1 mb-3">
            {MODES.map((mode) => {
              const unavailable = mode.value === 'prefer_cloud' && !cloudUsable;
              return (
                <button
                  key={mode.value}
                  type="button"
                  disabled={busy || unavailable}
                  onClick={() => void save({ routingPreference: mode.value })}
                  // Visible and disabled rather than absent: a missing option
                  // teaches the user that Zaram cannot do this at all. The two
                  // causes are named separately because they are different
                  // problems with different fixes.
                  title={
                    unavailable
                      ? hasCloudModel
                        ? 'Nothing may leave this device yet — allow it in Settings'
                        : 'No cloud provider is connected'
                      : undefined
                  }
                  className="flex-1 px-2 py-1 rounded text-[10px] transition-colors disabled:opacity-40"
                  style={{
                    background:
                      preference === mode.value ? 'rgba(34,211,238,0.14)' : 'transparent',
                    border: '1px solid rgba(255,255,255,0.07)',
                    color: preference === mode.value ? 'var(--color-cyan-light)' : '#94a3b8',
                  }}
                >
                  {mode.label}
                </button>
              );
            })}
          </div>

          <Section
            title="On this machine"
            empty="No chat model is installed here."
            models={local}
            pinned={pinned}
            busy={busy}
            loading={loading}
            onChoose={(name) => void save({ defaultModel: name })}
          />

          <Section
            title="Cloud"
            empty={
              hasCloudModel
                ? 'No cloud chat model was returned.'
                : 'No cloud provider is connected.'
            }
            models={cloud}
            pinned={pinned}
            busy={busy}
            loading={loading}
            showPolicy
            onChoose={(name) => void save({ defaultModel: name })}
          />

          {/* Named for what it is, and with the reason under it, because
              "a model I installed is missing" and "Zaram has not looked since
              it started" are indistinguishable from the outside. */}
          <button
            type="button"
            disabled={rescanning || loading}
            onClick={() => void rescan()}
            data-testid="routing-rescan"
            className="mt-1 flex items-center gap-1.5 text-[10px] text-slate-500 hover:text-slate-300 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={10} aria-hidden className={rescanning ? 'animate-spin' : ''} />
            {rescanning ? 'Looking again…' : 'Model missing? Look again'}
          </button>
          <p className="mt-0.5 text-[10px] leading-snug text-slate-600">
            Zaram lists what your model servers report. One started after Zaram
            is not seen until it looks again.
          </p>
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  empty,
  models,
  pinned,
  busy,
  loading,
  showPolicy = false,
  onChoose,
}: {
  title: string;
  empty: string;
  models: DiscoveredModel[];
  pinned: string | null;
  busy: boolean;
  loading: boolean;
  showPolicy?: boolean;
  onChoose: (name: string) => void;
}) {
  return (
    <div className="mb-3 last:mb-0">
      <p className="text-[10px] uppercase tracking-wide text-slate-500 mb-1">{title}</p>
      {loading && <p className="text-[10px] text-slate-600">Looking…</p>}
      {!loading && models.length === 0 && (
        <p className="text-[10px] text-slate-600">{empty}</p>
      )}
      {!loading &&
        models.map((model) => {
          const chosen = pinned === model.displayName;
          const slow = slowNote(model);
          return (
            <button
              key={model.id}
              type="button"
              disabled={busy}
              onClick={() => onChoose(chosen ? '' : model.displayName)}
              className="w-full text-left px-1.5 py-1 rounded hover:bg-white/5 transition-colors disabled:opacity-50 flex items-start gap-1.5"
            >
              <Check
                size={11}
                className="mt-[3px] shrink-0"
                style={{ color: chosen ? 'var(--color-cyan-light)' : 'transparent' }}
                aria-hidden
              />
              <span className="min-w-0">
                <span className="block text-[11px] text-slate-300 truncate">
                  {model.displayName}
                </span>
                {/* Both notes are the reason a person would choose differently,
                    so they sit under the name rather than in a tooltip. The
                    data policy is on the cloud list only — `CLAUDE.md` calls
                    naming the deal a primary feature of the picker, and it is
                    the whole question for a model that leaves the device. */}
                {slow && <span className="block text-[10px] text-amber-400/80">{slow}</span>}
                {showPolicy && (
                  <span className="block text-[10px] text-slate-500">
                    {describeDataPolicy(model.dataPolicy)}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      {/* Present in both lists, because handing the choice back is a choice. */}
      {!loading && models.length > 0 && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onChoose('')}
          className="w-full text-left px-1.5 py-1 rounded hover:bg-white/5 transition-colors disabled:opacity-50 flex items-center gap-1.5"
        >
          <Check
            size={11}
            className="shrink-0"
            style={{ color: pinned === null ? 'var(--color-cyan-light)' : 'transparent' }}
            aria-hidden
          />
          <span className="text-[11px] text-slate-500">Let Zaram decide</span>
        </button>
      )}
    </div>
  );
}
