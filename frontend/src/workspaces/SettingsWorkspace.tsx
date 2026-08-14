/**
 * Settings — the controls, and an honest statement where a control does not exist.
 *
 * The rule this screen was written around still holds: **where a capability is
 * missing, say so rather than presenting a switch that does nothing.** A
 * settings screen full of inert toggles tells the user they have control they
 * do not have, and on a privacy product that is the worst thing to be wrong
 * about.
 *
 * What changed is which side of that line things fall on. The previous version
 * reported "Egress log: not built" and "Kill switch: not built" — and the
 * egress log had been served at `/egress` for weeks, with its policy at
 * `/egress/policy`. **A screen can lie in both directions**, and "not built"
 * about something that exists is the more damaging one here: it tells a user
 * worried about their data that Zaram is not recording what leaves, when it is.
 * The kill switch genuinely did not exist, so it was built rather than
 * re-labelled.
 *
 * Where each control's authority lives
 * ------------------------------------
 * Backend, because more than one client has to agree about it: the chosen
 * model, the routing preference, the cloud connections, the per-host egress
 * policy, the kill switch. A phone or a second window must not hold a different
 * opinion about which provider may receive the user's documents.
 *
 * Browser, because it is a rendering choice this window owns: the renderer
 * (orb or avatar) and reduced motion. These are already `zustand` stores with
 * their own persistence and are surfaced here rather than duplicated.
 *
 * Discovery is on a button, not on mount
 * --------------------------------------
 * Listing models asks every connected cloud provider what it offers, which is
 * egress — logged, and refusable by policy. Rule 7g means that cannot happen
 * because a screen was opened. So the model list has a *Look for models*
 * action, and it says that it is a network call before it makes one.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Volume2,
  Shield,
  Cpu,
  RefreshCw,
  Check,
  Minus,
  Cloud,
  Eye,
  Plus,
  Trash2,
  Loader2,
  ExternalLink,
  AlertTriangle,
} from 'lucide-react';
import { useSystemStore } from '@/stores/systemStore';
import { useEmbodimentStore } from '@/stores/embodimentStore';
import {
  SettingsError,
  connectCloudProvider,
  disconnectCloudProvider,
  fetchCloudStatus,
  fetchEgressPolicy,
  fetchKillSwitch,
  fetchModels,
  fetchProviderCatalogue,
  fetchRoutingSettings,
  fetchWebSearch,
  forgetEgressPolicyForHost,
  setEgressPolicyForHost,
  setKillSwitch,
  setSearchScope,
  setWebSearch,
  updateRoutingSettings,
  type CatalogueProvider,
  type CloudStatus,
  type DiscoveredModel,
  type EgressMode,
  type EgressPolicy,
  type RoutingPreference,
  type RoutingSettings,
  type WebSearchStatus,
} from '@/services/settingsClient';

// --------------------------------------------------------------- primitives

function Row({
  label,
  value,
  detail,
  state = 'neutral',
  children,
}: {
  label: string;
  value?: string;
  detail?: React.ReactNode;
  state?: 'good' | 'neutral' | 'absent' | 'warn';
  children?: React.ReactNode;
}) {
  const colour =
    state === 'good'
      ? 'var(--color-emerald)'
      : state === 'warn'
        ? 'var(--color-amber, #fbbf24)'
        : state === 'absent'
          ? 'var(--color-text-faint)'
          : 'var(--color-text-muted)';
  return (
    <div
      className="flex items-start gap-3 px-5 py-3.5"
      style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
    >
      <span className="mt-0.5 shrink-0" style={{ color: colour }}>
        {state === 'good' ? <Check size={14} /> : state === 'warn' ? <AlertTriangle size={14} /> : <Minus size={14} />}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="text-sm" style={{ color: 'var(--color-text)' }}>
            {label}
          </span>
          {value && (
            <span className="text-xs" style={{ fontFamily: 'var(--font-mono)', color: colour }}>
              {value}
            </span>
          )}
        </div>
        {detail && (
          // pre-wrap so a detail can carry an indented command block. Without
          // it install instructions collapse onto one line and stop being
          // copyable as a command.
          <div
            className="mt-1 text-[11px] text-slate-500 leading-relaxed"
            style={{ whiteSpace: 'pre-wrap' }}
          >
            {detail}
          </div>
        )}
        {children && <div className="mt-2.5">{children}</div>}
      </div>
    </div>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div
      className="rounded-xl overflow-hidden mb-4"
      style={{ border: '1px solid var(--color-border-subtle)', background: 'var(--color-glass)' }}
    >
      <div
        className="flex items-center gap-2 px-5 py-3"
        style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
      >
        {icon}
        <span
          className="text-xs uppercase tracking-wider"
          style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-display)' }}
        >
          {title}
        </span>
      </div>
      {children}
    </div>
  );
}

/**
 * One destination and what happens to requests addressed to it.
 *
 * Shared by the hosts that have a rule and the hosts that have only been
 * contacted, because they are the same decision at two stages and drawing them
 * differently made the controls sit at three different x positions down one
 * list. The host gets a fixed width and truncates rather than pushing the
 * control, so the segmented buttons form a column the eye can run down — which
 * is what makes "what can leave this machine" answerable at a glance rather
 * than by reading every row.
 */
function PolicyRow({
  host,
  mode,
  ruled,
  busy,
  onChange,
  onForget,
}: {
  host: string;
  mode: EgressMode;
  ruled: boolean;
  busy: boolean;
  onChange: (mode: EgressMode) => void;
  onForget?: () => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <span
        className="text-[11px] w-44 shrink-0 truncate"
        title={host}
        style={{
          fontFamily: 'var(--font-mono)',
          color: ruled ? 'var(--color-text)' : 'var(--color-text-faint)',
        }}
      >
        {host}
      </span>
      <Segmented<EgressMode>
        options={[
          { value: 'deny', label: 'Never' },
          { value: 'ask', label: 'Ask' },
          { value: 'allow', label: 'Always' },
        ]}
        value={mode}
        disabled={busy}
        onChange={onChange}
      />
      {ruled ? (
        <button
          aria-label={`Forget the rule for ${host}`}
          className="p-1 rounded text-slate-500 hover:text-slate-300"
          onClick={onForget}
        >
          <Trash2 size={12} />
        </button>
      ) : (
        <span className="text-[10px] text-slate-500">contacted, no rule</span>
      )}
    </div>
  );
}

/** A segmented control. Used wherever the choice is a small closed set, which
 *  `CLAUDE.md` prefers to a slider for anyone non-technical: nobody holds an
 *  opinion about 0.3 versus 0.4 on a bias slider. */
function Segmented<T extends string>({
  options,
  value,
  onChange,
  disabled,
}: {
  options: Array<{ value: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex rounded-lg overflow-hidden" style={{ border: '1px solid var(--color-border-subtle)' }}>
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className="px-3 py-1.5 text-xs transition-colors disabled:opacity-40"
            style={{
              background: active ? 'var(--color-indigo-light, #6366f1)' : 'transparent',
              color: active ? '#fff' : 'var(--color-text-muted)',
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function Button({
  children,
  onClick,
  busy,
  disabled,
  tone = 'normal',
  type = 'button',
}: {
  children: React.ReactNode;
  onClick?: () => void;
  busy?: boolean;
  disabled?: boolean;
  tone?: 'normal' | 'danger';
  type?: 'button' | 'submit';
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || busy}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors disabled:opacity-40"
      style={{
        border: '1px solid var(--color-border-subtle)',
        color: tone === 'danger' ? '#fca5a5' : 'var(--color-text)',
      }}
    >
      {busy && <Loader2 size={12} className="animate-spin" />}
      {children}
    </button>
  );
}

/** A failure shown in the user's terms, using the backend's own sentence. */
function Problem({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="mt-2 text-[11px] leading-relaxed" style={{ color: '#fca5a5' }}>
      {message}
    </p>
  );
}

const messageOf = (error: unknown): string =>
  error instanceof SettingsError || error instanceof Error
    ? error.message
    : 'Something went wrong.';

// ------------------------------------------------------------------- screen

export default function SettingsWorkspace() {
  const backendOnline = useSystemStore((s) => s.backendOnline);
  const routing = useSystemStore((s) => s.routing);
  const speech = useSystemStore((s) => s.speech);
  const refresh = useSystemStore((s) => s.refresh);
  const startPolling = useSystemStore((s) => s.startPolling);

  const renderer = useEmbodimentStore((s) => s.renderer);
  const setRenderer = useEmbodimentStore((s) => s.setRenderer);

  const [catalogue, setCatalogue] = useState<CatalogueProvider[]>([]);
  const [catalogueDate, setCatalogueDate] = useState<string>('');
  const [cloud, setCloud] = useState<CloudStatus | null>(null);
  const [routingSettings, setRoutingSettings] = useState<RoutingSettings | null>(null);
  const [killSwitch, setKillSwitchState] = useState<boolean | null>(null);
  const [policy, setPolicy] = useState<EgressPolicy | null>(null);
  const [models, setModels] = useState<DiscoveredModel[] | null>(null);
  const [search, setSearch] = useState<WebSearchStatus | null>(null);

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // The provider being connected, and the key being typed for it. Held here
  // rather than in a child so that switching provider clears the field — a key
  // left over from a different provider is the kind of thing that gets pasted
  // into the wrong service.
  const [chosenProvider, setChosenProvider] = useState<string>('');
  const [apiKey, setApiKey] = useState('');
  const [customUrl, setCustomUrl] = useState('');

  useEffect(() => startPolling(), [startPolling]);

  /**
   * Everything that costs nothing to read. Deliberately excludes the model
   * list, which is egress — see the header.
   *
   * **Settled, not all.** With `Promise.all`, one endpoint failing threw before
   * a single `setState` ran, so the entire screen stayed empty — every provider
   * gone, every rule gone, every toggle inert — and the only clue was one error
   * banner. That happened here for real the first time `/search/web` was added
   * without its proxy entry: a route nobody could reach blanked the provider
   * picker, the egress rules and the kill switch along with it.
   *
   * A settings screen is six independent readings of the system. One of them
   * being unavailable is a reason to say so about *that* one, never a reason to
   * stop reporting the other five — the same principle as the rest of this
   * screen, applied to its own loading.
   */
  const loadLocalState = useCallback(async () => {
    setError(null);

    const [cat, cloudStatus, routingState, kill, egressPolicy, webSearch] =
      await Promise.allSettled([
        fetchProviderCatalogue(),
        fetchCloudStatus(),
        fetchRoutingSettings(),
        fetchKillSwitch(),
        fetchEgressPolicy(),
        fetchWebSearch(),
      ]);

    if (cat.status === 'fulfilled') {
      setCatalogue(cat.value.providers);
      setCatalogueDate(cat.value.generated);
    }
    if (cloudStatus.status === 'fulfilled') setCloud(cloudStatus.value);
    if (routingState.status === 'fulfilled') setRoutingSettings(routingState.value);
    if (kill.status === 'fulfilled') setKillSwitchState(kill.value);
    if (egressPolicy.status === 'fulfilled') setPolicy(egressPolicy.value);
    if (webSearch.status === 'fulfilled') setSearch(webSearch.value);

    // Named, and only the ones that actually failed. "Something went wrong"
    // over a screen that is now half-populated is worse than either a working
    // screen or an empty one, because the user cannot tell which half to trust.
    const failures = [
      ['providers', cat],
      ['cloud', cloudStatus],
      ['routing', routingState],
      ['kill switch', kill],
      ['per-source rules', egressPolicy],
      ['web search', webSearch],
    ] as const;
    const broken = failures.filter(([, r]) => r.status === 'rejected');
    if (broken.length > 0) {
      setError(
        `Could not read ${broken.map(([name]) => name).join(', ')} — ` +
          messageOf((broken[0][1] as PromiseRejectedResult).reason) +
          ' Everything else on this screen is current.',
      );
    }
  }, []);

  useEffect(() => {
    void loadLocalState();
  }, [loadLocalState]);

  const run = async (name: string, work: () => Promise<void>) => {
    setBusy(name);
    setError(null);
    try {
      await work();
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(null);
    }
  };

  const selected = catalogue.find((p) => p.id === chosenProvider) ?? null;
  const needsKey = selected ? selected.auth !== 'none' : true;
  const needsUrl = selected ? !selected.available : Boolean(chosenProvider === '');

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-8 pt-6 pb-4 flex items-center gap-3">
        <h1
          className="text-lg font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}
        >
          Settings
        </h1>
        <div className="flex-1" />
        <button
          onClick={() => {
            void refresh();
            void loadLocalState();
          }}
          aria-label="Refresh"
          className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-colors"
        >
          <RefreshCw size={15} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-8 pb-8 max-w-3xl">
        {error && (
          <div
            className="mb-4 px-4 py-3 rounded-lg text-xs"
            style={{ border: '1px solid rgba(248,113,113,0.4)', color: '#fca5a5' }}
            role="alert"
          >
            {error}
          </div>
        )}

        {/* ------------------------------------------------------- Privacy */}
        <Section title="Privacy" icon={<Shield size={14} style={{ color: 'var(--color-emerald)' }} />}>
          <Row
            label="Kill switch"
            value={killSwitch === null ? 'unknown' : killSwitch ? 'ON — nothing may leave' : 'off'}
            state={killSwitch ? 'warn' : 'neutral'}
            detail={
              'Refuses every outbound request in one action, whatever the per-source rules say. ' +
              'Turning it off restores those rules exactly as they were — nothing is forgotten.\n' +
              'The local model is unaffected: it runs on this machine, so there is nothing to cut.'
            }
          >
            <Segmented<'on' | 'off'>
              options={[
                { value: 'off', label: 'Allow, per the rules below' },
                { value: 'on', label: 'Cut everything' },
              ]}
              value={killSwitch ? 'on' : 'off'}
              disabled={busy === 'kill' || killSwitch === null}
              onChange={(next) =>
                void run('kill', async () => {
                  setKillSwitchState(await setKillSwitch(next === 'on'));
                  // The web search row reports the kill switch as one of the
                  // things standing in its way, so leaving it unrefreshed would
                  // show a warning that had stopped being true — or hide one
                  // that had just started being true.
                  setSearch(await fetchWebSearch());
                })
              }
            />
          </Row>

          <Row
            label="Requests that can leave this device"
            value={routing?.canLeaveDevice ? 'some' : 'none'}
            state={routing?.canLeaveDevice ? 'neutral' : 'good'}
            detail={
              routing?.canLeaveDevice
                ? 'A route off this machine exists. Everything that took it is listed in Activity.'
                : 'Inference runs locally and the Spine is a file on this disk. Nothing is sent out.'
            }
          />

          <Row
            label="Per-source rules"
            value={policy ? `${Object.keys(policy.rules).length} set · default deny` : 'unknown'}
            state="good"
            detail="Each destination is allowed, asked about, or refused. Anything with no rule is refused."
          >
            <div className="flex flex-col gap-1.5">
              {policy &&
                Object.entries(policy.rules).map(([host, mode]) => (
                  <PolicyRow
                    key={host}
                    host={host}
                    mode={mode}
                    ruled
                    busy={busy === `policy:${host}`}
                    onChange={(next) =>
                      void run(`policy:${host}`, async () => {
                        await setEgressPolicyForHost(host, next);
                        setPolicy(await fetchEgressPolicy());
                        setSearch(await fetchWebSearch());
                      })
                    }
                    onForget={() =>
                      void run(`policy:${host}`, async () => {
                        await forgetEgressPolicyForHost(host);
                        setPolicy(await fetchEgressPolicy());
                        setSearch(await fetchWebSearch());
                      })
                    }
                  />
                ))}

              {policy?.hostsWithoutARule.map((host) => (
                <PolicyRow
                  key={host}
                  host={host}
                  // Shown as "Never" because that is what happens to it — the
                  // default is deny. Showing it as unset would be accurate
                  // about the rule and wrong about the behaviour, and the
                  // behaviour is the thing the user is checking.
                  mode="deny"
                  ruled={false}
                  busy={busy === `policy:${host}`}
                  onChange={(next) =>
                    void run(`policy:${host}`, async () => {
                      await setEgressPolicyForHost(host, next);
                      setPolicy(await fetchEgressPolicy());
                        setSearch(await fetchWebSearch());
                    })
                  }
                />
              ))}

              {policy && Object.keys(policy.rules).length === 0 && policy.hostsWithoutARule.length === 0 && (
                <span className="text-[11px] text-slate-500">
                  Nothing has been contacted yet, so there is nothing to decide about.
                </span>
              )}
            </div>
          </Row>

          <Row
            label="Web search"
            value={search === null ? 'unknown' : search.on ? 'on' : 'off'}
            state={search?.on ? 'neutral' : 'good'}
            detail={
              'Zaram’s first source that leaves this machine, and it is governed like any other: ' +
              'the question itself is what gets sent, never anything recalled from your Spine.'
            }
          >
            {/* A testid because "On" and "Off" are the two most reusable button
                labels there are, and a driver script matching them by name
                would silently start operating a different control the day one
                is added above. */}
            <div className="flex flex-col gap-2" data-testid="web-search-toggle">
              <Segmented<'on' | 'off'>
                options={[
                  { value: 'off', label: 'Off' },
                  { value: 'on', label: 'On' },
                ]}
                value={search?.on ? 'on' : 'off'}
                disabled={busy === 'search' || search === null || search.forcedByEnvironment}
                onChange={(next) =>
                  void run('search', async () => setSearch(await setWebSearch(next === 'on')))
                }
              />

              {/* The two things that still stand between "on" and a working
                  search, each stated only when it actually applies. Turning the
                  switch on and getting a refusal, with nothing explaining why,
                  is the failure this section exists to prevent. */}
              {search?.forcedByEnvironment && (
                <p className="text-[11px] leading-relaxed" style={{ color: 'var(--color-amber, #fbbf24)' }}>
                  ZARAM_WEB_SEARCH is set in the environment, so it decides and this control does
                  not. Unset it to hand the choice back to this screen.
                </p>
              )}

              {search?.on && search.killSwitch && (
                <p className="text-[11px] leading-relaxed" style={{ color: 'var(--color-amber, #fbbf24)' }}>
                  The kill switch is on, so no search will be sent regardless.
                </p>
              )}

              {/* When searching is worth it, which is a different question from
                  whether it is allowed. Search compensates for what the
                  answering model does not know, and a local model knows least —
                  so the default only searches for local models. Shown only when
                  search is on, because it is meaningless otherwise. */}
              {search?.on && (
                <div className="flex flex-col gap-1">
                  <Segmented<'local_only' | 'always'>
                    options={[
                      { value: 'local_only', label: 'Only for local models' },
                      { value: 'always', label: 'For every model' },
                    ]}
                    value={search.scope}
                    disabled={busy === 'search-scope'}
                    onChange={(next) =>
                      void run('search-scope', async () => setSearch(await setSearchScope(next)))
                    }
                  />
                  <span className="text-[10px] text-slate-500 leading-relaxed">
                    A local model has an older, smaller store of facts, so a live result changes
                    its answer far more often. Cloud models mostly do not come with web search
                    either — they just have a later cutoff — so this trades freshness for speed
                    rather than avoiding something the provider would have done anyway.
                  </span>
                </div>
              )}

              {search?.on && search.hostPolicy === 'deny' && !search.killSwitch && (
                <p className="text-[11px] leading-relaxed" style={{ color: 'var(--color-amber, #fbbf24)' }}>
                  Searches go to {search.host}, which has no rule yet — so they are refused, and the
                  refusal is recorded in Activity. Set that host to Ask or Always in Per-source
                  rules above to let them through. Turning search on does not grant a destination
                  anything; that stays a separate decision.
                </p>
              )}
            </div>
          </Row>
        </Section>

        {/* -------------------------------------------------------- Models */}
        <Section title="Models" icon={<Cpu size={14} style={{ color: 'var(--color-indigo-light)' }} />}>
          <Row
            label="Engine"
            value={backendOnline ? 'running' : 'offline'}
            state={backendOnline ? 'good' : 'absent'}
            detail={backendOnline ? undefined : 'Zaram’s backend is not reachable on port 8420.'}
          />

          <Row
            label="How Zaram chooses"
            value={routingSettings?.routingPreference ?? 'unknown'}
            state="good"
            detail={
              'A bias, not a permission. Preferring cloud cannot promote a model whose terms are ' +
              'unknown — that gate is separate and a dropdown does not turn it off.'
            }
          >
            <Segmented<RoutingPreference>
              options={[
                { value: 'prefer_local', label: 'Prefer local' },
                { value: 'auto', label: 'Auto' },
                { value: 'prefer_cloud', label: 'Prefer cloud' },
              ]}
              value={routingSettings?.routingPreference ?? 'auto'}
              disabled={busy === 'routing' || !routingSettings}
              onChange={(next) =>
                void run('routing', async () =>
                  setRoutingSettings(await updateRoutingSettings({ routingPreference: next })),
                )
              }
            />
          </Row>

          <Row
            label="Which model answers"
            value={routingSettings?.defaultModel ?? 'Zaram decides'}
            state={routingSettings?.defaultModel ? 'good' : 'neutral'}
            detail={
              models === null
                ? 'Looking for models asks every connected provider what it offers. For a cloud provider that is a request that leaves this device, so it happens when you ask for it and is recorded in Activity.'
                : 'Leaving this on “Zaram decides” uses the model the provider layer vetted — it checks that the model fits alongside the embedding model and that its terms are known.'
            }
          >
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  busy={busy === 'models'}
                  onClick={() => void run('models', async () => setModels(await fetchModels()))}
                >
                  <RefreshCw size={12} />
                  {models === null ? 'Look for models' : 'Look again'}
                </Button>
                {models !== null && (
                  <span className="text-[11px] text-slate-500">{models.length} found</span>
                )}
              </div>

              {models !== null && (
                <select
                  aria-label="Which model answers"
                  className="px-2 py-1.5 rounded-lg text-xs max-w-full"
                  style={{
                    background: 'transparent',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                  }}
                  value={routingSettings?.defaultModel ?? ''}
                  onChange={(event) =>
                    void run('routing', async () =>
                      setRoutingSettings(
                        await updateRoutingSettings({ defaultModel: event.target.value }),
                      ),
                    )
                  }
                >
                  <option value="">Zaram decides</option>
                  {models.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.displayName} — {model.locality}
                      {model.dataPolicy ? '' : ' · terms unknown'}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </Row>
        </Section>

        {/* --------------------------------------------------------- Cloud */}
        <Section title="Cloud providers" icon={<Cloud size={14} style={{ color: 'var(--color-indigo-light)' }} />}>
          <Row
            label="Connected"
            value={cloud ? `${cloud.connections.length}` : 'unknown'}
            state={cloud?.configured ? 'good' : 'neutral'}
            detail={
              'Zaram never buys inference — bring your own key. Connecting stores it and makes no ' +
              'network call: a key is checked by being used, and that first use is logged and confirmed.'
            }
          >
            <div className="flex flex-col gap-1.5">
              {cloud?.connections.map((connection) => (
                <div key={connection.providerId} className="flex items-center gap-2 flex-wrap">
                  <span className="text-[11px]" style={{ color: 'var(--color-text)' }}>
                    {connection.displayName}
                  </span>
                  <span
                    className="text-[10px]"
                    style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}
                  >
                    {connection.baseUrl}
                  </span>
                  {connection.keyTail && (
                    <span className="text-[10px] text-slate-500">key ····{connection.keyTail}</span>
                  )}
                  <Button
                    tone="danger"
                    busy={busy === `disconnect:${connection.providerId}`}
                    onClick={() =>
                      void run(`disconnect:${connection.providerId}`, async () =>
                        setCloud(await disconnectCloudProvider(connection.providerId)),
                      )
                    }
                  >
                    Disconnect
                  </Button>
                </div>
              ))}
              {cloud && cloud.connections.length === 0 && (
                <span className="text-[11px] text-slate-500">
                  None. Everything is answered on this machine.
                </span>
              )}

              {/* The step that is missing after a successful connect, named.
                  Connecting stores a key; it does not permit the destination.
                  So "Look for models" is refused by default deny, the list
                  comes back empty, and there is no way to select a cloud model
                  — with nothing on screen explaining why. That happened to the
                  maintainer, and this is the fix: say which host needs a rule
                  and offer it here rather than sending them to another
                  section to guess. */}
              {cloud?.connections
                .filter((c) => c.locality === 'cloud')
                .map((c) => {
                  const host = (() => {
                    try {
                      return new URL(c.baseUrl).hostname;
                    } catch {
                      return '';
                    }
                  })();
                  const rule = host ? policy?.rules[host] : undefined;
                  if (!host || (rule && rule !== 'deny')) return null;
                  return (
                    <p
                      key={`needs-rule-${c.providerId}`}
                      className="text-[11px] leading-relaxed"
                      style={{ color: 'var(--color-amber, #fbbf24)' }}
                    >
                      {c.displayName} is connected, but {host} has no rule yet — so looking for
                      its models, and any answer from it, will be refused and recorded in
                      Activity. Allow it below to use it.
                      <button
                        type="button"
                        className="ml-2 underline"
                        onClick={() =>
                          void run(`policy:${host}`, async () => {
                            await setEgressPolicyForHost(host, 'allow');
                            setPolicy(await fetchEgressPolicy());
                            setSearch(await fetchWebSearch());
                          })
                        }
                      >
                        Allow {host}
                      </button>
                    </p>
                  );
                })}
            </div>
          </Row>

          <Row
            label="Connect a provider"
            detail={
              catalogueDate
                ? `Addresses were read from each provider's documentation on ${catalogueDate}. Nothing here was confirmed by a live request.`
                : undefined
            }
          >
            <form
              className="flex flex-col gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                void run('connect', async () => {
                  setCloud(
                    await connectCloudProvider({
                      providerId: chosenProvider || undefined,
                      baseUrl: customUrl.trim() || undefined,
                      apiKey: apiKey.trim() || undefined,
                    }),
                  );
                  setApiKey('');
                  setCustomUrl('');
                });
              }}
            >
              <select
                aria-label="Provider"
                className="px-2 py-1.5 rounded-lg text-xs"
                style={{
                  background: 'transparent',
                  border: '1px solid var(--color-border-subtle)',
                  color: 'var(--color-text)',
                }}
                value={chosenProvider}
                onChange={(event) => {
                  setChosenProvider(event.target.value);
                  // A key typed for one provider must not survive into
                  // another. Pasting a key into the wrong service is a real
                  // way to leak a credential to a third party.
                  setApiKey('');
                  setCustomUrl('');
                }}
              >
                <option value="">Something else — I'll paste the address</option>
                {catalogue.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.displayName}
                    {provider.available ? '' : ' — not reachable yet'}
                  </option>
                ))}
              </select>

              {/* The grading, in the user's words, at the moment they picked
                  it. `CLAUDE.md`: unavailable entries are shown greyed out and
                  honestly graded — "greyed out" without "and here is why" is
                  the same as missing. */}
              {selected && !selected.available && (
                <p className="text-[11px] leading-relaxed" style={{ color: 'var(--color-amber, #fbbf24)' }}>
                  {selected.note}
                </p>
              )}

              {(needsUrl || (selected && !selected.available)) && (
                <input
                  aria-label="API address"
                  placeholder="https://… the API address from your provider's console"
                  className="px-2 py-1.5 rounded-lg text-xs"
                  style={{
                    background: 'transparent',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                  }}
                  value={customUrl}
                  onChange={(event) => setCustomUrl(event.target.value)}
                />
              )}

              {needsKey && (
                <input
                  aria-label="API key"
                  type="password"
                  autoComplete="off"
                  placeholder="Your API key"
                  className="px-2 py-1.5 rounded-lg text-xs"
                  style={{
                    background: 'transparent',
                    border: '1px solid var(--color-border-subtle)',
                    color: 'var(--color-text)',
                  }}
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                />
              )}

              <div className="flex items-center gap-2 flex-wrap">
                <Button type="submit" busy={busy === 'connect'}>
                  <Plus size={12} />
                  Connect
                </Button>
                {selected?.keyUrl && (
                  <a
                    href={selected.keyUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200"
                  >
                    <ExternalLink size={11} />
                    Where to get a key
                  </a>
                )}
              </div>
            </form>
          </Row>
        </Section>

        {/* -------------------------------------------------------- Speech */}
        <Section title="Speech" icon={<Volume2 size={14} style={{ color: 'var(--color-indigo-light)' }} />}>
          <Row
            label="Speech synthesis"
            value={speech === null ? 'unknown' : speech === 'available' ? 'available' : 'not installed'}
            state={speech === 'available' ? 'good' : speech === null ? 'neutral' : 'absent'}
            detail={
              speech === null
                ? 'Waiting for the backend to report.'
                : speech === 'available'
                  ? 'Kokoro is installed and runs on the CPU, so it does not compete with the local model for VRAM. Replies are spoken when the avatar is showing — one decision, made by choosing a face.'
                  : 'Voice ships as an optional extra because it pulls roughly 830 MB — torch, ' +
                    'transformers and the spaCy stack. Chat is unaffected. To enable it:\n\n' +
                    '    pip install -r backend/requirements-voice.txt\n' +
                    '    python -m spacy download en_core_web_sm'
            }
          />
        </Section>

        {/* ---------------------------------------------------- Appearance */}
        <Section title="Appearance" icon={<Eye size={14} style={{ color: 'var(--color-indigo-light)' }} />}>
          <Row
            label="Indicator"
            value={renderer}
            state="good"
            detail={
              'The orb and the avatar are two renderings of one state — neither knows the other ' +
              'exists. The avatar embodies what the system is doing, not who it is. ' +
              'Choosing it also turns on spoken replies.'
            }
          >
            <Segmented<'orb' | 'avatar'>
              options={[
                { value: 'orb', label: 'Orb' },
                { value: 'avatar', label: 'Avatar' },
              ]}
              value={renderer}
              onChange={setRenderer}
            />
          </Row>
        </Section>

        <p className="text-[11px] text-slate-500 leading-relaxed px-1">
          Every value on this screen is read from the running backend or from this window's own
          state. Where a control is missing it says so rather than showing a switch that does
          nothing.
        </p>
        <Problem message={null} />
      </div>
    </div>
  );
}
