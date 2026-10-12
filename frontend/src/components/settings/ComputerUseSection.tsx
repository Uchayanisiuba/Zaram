/**
 * Computer Use — desktop automation via cua-driver.
 *
 * This section surfaces the cua-driver MCP server with its platform-specific
 * install status, permission checks, and quick actions. It follows the same
 * pattern as ToolsSection but adds computer-use specific UI.
 *
 * Using it is local: its tools act on this machine and are governed by the MCP
 * policy gate -- read-only tools run freely, mutative tools confirm once.
 * **Installing it is not local**: the install downloads a program from github.com,
 * and the section says so beside the button.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  fetchServers,
  fetchServerTools,
  pinTools,
  installCuaDriver,
  fetchCuaHealth,
  setServerEnabled,
  type CuaHealth,
  type ServerTool,
  type ToolServer,
  type CuaDriverInstallStatus,
} from '../../services/toolsClient';
import { ComputerUseAction } from './ComputerUseActions';

export interface ComputerUseSectionProps {
  Row: React.ComponentType<{
    label: string;
    value?: string;
    detail?: React.ReactNode;
    state?: 'good' | 'neutral' | 'absent' | 'warn';
    children?: React.ReactNode;
  }>;
}

const CUASERVER_IDS = ['cua-driver', 'cua'];

/** Check if a server is a cua-driver instance. */
function isCuaDriver(server: ToolServer): boolean {
  return CUASERVER_IDS.some((id) => server.id.toLowerCase().includes(id));
}

/** What the driver said about itself, in a sentence.
 *
 *  This read `server.cuaHealth`, which nothing ever filled in, so every driver said
 *  "Health check not available" forever. It now reads the answer from
 *  `/tools/cua-driver/health`, which asks the driver's own `health_report`. */
function getCuaStatus(health: CuaHealth | undefined, enabled = true): {
  status: 'healthy' | 'permissions_needed' | 'not_connected' | 'error' | 'unknown' | 'off';
  detail: string;
} {
  if (!enabled) {
    return {
      status: 'off',
      detail:
        'Switched off. Zaram offers the model none of its tools and refuses any call to it, and nothing ' +
        'is running. What you allowed and the program itself are kept, so switching it on is instant.',
    };
  }
  if (!health) {
    return { status: 'unknown', detail: 'Checking whether it can act on this machine…' };
  }
  switch (health.status) {
    case 'healthy':
      return {
        status: 'healthy',
        detail: `Ready${health.version ? ` (cua-driver ${health.version})` : ''}: it can read windows and act on them.`,
      };
    case 'permissions_needed':
      return {
        status: 'permissions_needed',
        detail: health.detail || 'The driver needs a system permission before it can act.',
      };
    case 'not_connected':
      return { status: 'not_connected', detail: health.error || 'Zaram could not start it.' };
    case 'error':
      return { status: 'error', detail: health.error ?? 'It did not say why.' };
    default:
      return { status: 'unknown', detail: 'It did not say.' };
  }
}

export default function ComputerUseSection({ Row }: ComputerUseSectionProps) {
  const [servers, setServers] = useState<ToolServer[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cuatools, setCuaTools] = useState<ServerTool[] | null>(null);
  // Which server the listed tools belong to. `ServerTool` carries no server id.
  const [cuatoolsFor, setCuaToolsFor] = useState<string | null>(null);
  const [health, setHealth] = useState<Record<string, CuaHealth>>({});

  const checkHealth = useCallback(async (serverId: string) => {
    const answer = await fetchCuaHealth(serverId).catch(
      (caught: Error): CuaHealth => ({ status: 'error', error: caught.message }),
    );
    setHealth((now) => ({ ...now, [serverId]: answer }));
  }, []);

  const reload = useCallback(async () => {
    try {
      const all = await fetchServers();
      setServers(all);
      setLoadError(null);
    } catch (caught) {
      setServers(null);
      setLoadError((caught as Error).message);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const cuaServers = servers?.filter(isCuaDriver) ?? [];
  const cuaIds = cuaServers.map((s) => s.id).join(',');

  // Asked once per server as soon as it is listed, so the row says something true
  // without anyone having to press a button first.
  useEffect(() => {
    for (const id of cuaIds ? cuaIds.split(',') : []) {
      const on = servers?.find((s) => s.id === id)?.enabled !== false;
      if (on && !(id in health)) void checkHealth(id);
    }
  }, [cuaIds, health, checkHealth, servers]);

  const toggle = useCallback(
    async (serverId: string, enabled: boolean) => {
      setBusy(`toggle:${serverId}`);
      setError(null);
      try {
        await setServerEnabled(serverId, enabled);
        // Off clears what the driver last said about itself; on asks it again.
        setHealth((now) => {
          const next = { ...now };
          delete next[serverId];
          return next;
        });
        await reload();
      } catch (caught) {
        setError((caught as Error).message);
      } finally {
        setBusy(null);
      }
    },
    [reload],
  );

  const runHealthCheck = useCallback(
    async (serverId: string) => {
      setBusy(`health:${serverId}`);
      setError(null);
      try {
        await reload();
        await checkHealth(serverId);
      } catch (caught) {
        setError((caught as Error).message);
      } finally {
        setBusy(null);
      }
    },
    [reload, checkHealth],
  );

  const loadTools = useCallback(
    async (serverId: string) => {
      setBusy(`tools:${serverId}`);
      try {
        const tools = await fetchServerTools(serverId);
        setCuaTools(tools);
        setCuaToolsFor(serverId);
      } catch (caught) {
        setCuaTools(null);
        setCuaToolsFor(null);
        setError((caught as Error).message);
      } finally {
        setBusy(null);
      }
    },
    [],
  );

  const togglePin = useCallback(
    async (serverId: string, name: string, currentPins: string[]) => {
      const next = currentPins.includes(name)
        ? currentPins.filter((n) => n !== name)
        : [...currentPins, name];
      try {
        await pinTools(serverId, next);
        await reload();
      } catch (caught) {
        setError((caught as Error).message);
      }
    },
    [reload],
  );

  const [installStatus, setInstallStatus] = useState<CuaDriverInstallStatus | null>(null);

  const installCua = useCallback(async () => {
    setBusy('install');
    setError(null);
    setInstallStatus({
      status: 'downloading',
      progress: 0,
      message: 'Downloading about 30 MB from github.com. This can take a few minutes.',
      error: '',
    });
    
    try {
      const result = await installCuaDriver('latest');
      setInstallStatus(result);
      if (result.status === 'complete') {
        // Refresh servers to show the newly installed cua-driver
        await reload();
      } else if (result.status === 'error') {
        setError(result.error);
      }
    } catch (caught) {
      const errorMsg = (caught as Error).message;
      setError(errorMsg);
      setInstallStatus({ status: 'error', progress: 0, message: '', error: errorMsg });
    } finally {
      setBusy(null);
    }
  }, [reload]);

  return (
    <>
      <Row
        label="Computer Use"
        value={
          servers === null
            ? 'unknown'
            : cuaServers.length === 0
            ? 'not installed'
            : cuaServers.every((s) => !s.enabled)
            ? 'off'
            : cuaServers.length === 1
            ? '1 server'
            : `${cuaServers.length} servers`
        }
        state={
          servers === null
            ? 'warn'
            : cuaServers.length === 0
            ? 'absent'
            : cuaServers.some((s) => getCuaStatus(health[s.id], s.enabled).status === 'healthy')
            ? 'good'
            : cuaServers.some((s) => getCuaStatus(health[s.id], s.enabled).status === 'permissions_needed')
            ? 'warn'
            : 'neutral'
        }
        detail={
          <span>
            Control native desktop apps (click, type, scroll, screenshot) via the cua-driver
            MCP server. Works on macOS, Windows, and Linux in the background.
          </span>
        }
      >
        {cuaServers.length === 0 && (
          <div className="px-5 py-3 space-y-3">
            <Row
              label="Install cua-driver"
              value={installStatus?.status === 'complete' ? 'installed' : 'not installed'}
              state={installStatus?.status === 'error' ? 'warn' : installStatus?.status === 'complete' ? 'good' : 'absent'}
              detail={
                <>
                  {installStatus && (
                    <div className="flex flex-col gap-2 mt-2">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 rounded-full bg-white/10 overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-300"
                            style={{
                              width: `${(installStatus.progress || 0) * 100}%`,
                              backgroundColor:
                                installStatus.status === 'error'
                                  ? 'var(--color-red)'
                                  : installStatus.status === 'complete'
                                  ? 'var(--color-emerald)'
                                  : 'var(--color-cyan)',
                            }}
                          />
                        </div>
                        <span className="text-xs font-mono" style={{ color: 'var(--color-text-muted)', minWidth: '40px' }}>
                          {Math.round((installStatus.progress || 0) * 100)}%
                        </span>
                      </div>
                      <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                        {installStatus.message || installStatus.error || 'Installing...'}
                      </span>
                    </div>
                  )}
                </>
              }
            >
              <div className="flex flex-col gap-2 mt-2">
                <button
                  type="button"
                  onClick={installCua}
                  disabled={busy === 'install' || installStatus?.status === 'downloading' || installStatus?.status === 'installing'}
                  className="self-start text-xs px-2.5 py-1.5 rounded"
                  style={{
                    color: 'var(--color-text)',
                    border: '1px solid var(--color-border-subtle)',
                    opacity: busy === 'install' || installStatus?.status === 'downloading' || installStatus?.status === 'installing' ? 0.5 : 1,
                  }}
                >
                  {installStatus?.status === 'downloading'
                    ? 'Downloading...'
                    : installStatus?.status === 'installing'
                    ? 'Installing...'
                    : installStatus?.status === 'complete'
                    ? 'Installed ✓'
                    : installStatus?.status === 'error'
                    ? 'Retry'
                    : 'Install cua-driver'}
                </button>
                {!installStatus && (
                  <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    Downloads cua-driver 0.34.1 from github.com (trycua/cua), about 30 MB, which can take a few
                    minutes. Pressing Install is your permission for that one download; it is logged, and the
                    file is checked against a checksum built into this version before anything is unpacked.
                    Zaram then connects it as a tool with the driver&apos;s own telemetry switched off. Anything
                    that changes something on your screen asks first.
                  </span>
                )}
              </div>
            </Row>
          </div>
        )}

        {cuaServers.map((server) => {
          const status = getCuaStatus(health[server.id], server.enabled);
          const isHealthy = status.status === 'healthy';
          const needsPerms = status.status === 'permissions_needed';

          return (
            <div
              key={server.id}
              className="flex flex-col gap-1.5 px-5 py-3"
              style={{ borderTop: '1px solid var(--color-border-subtle)' }}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm truncate" style={{ color: 'var(--color-text)' }}>
                    {server.id}
                  </span>
                  <span
                    className="text-xs uppercase tracking-wider px-1.5 py-0.5 rounded"
                    style={{
                      color:
                        isHealthy
                          ? 'var(--color-emerald)'
                          : needsPerms
                          ? 'var(--color-amber)'
                          : 'var(--color-text-muted)',
                      border: '1px solid var(--color-border-subtle)',
                    }}
                  >
                    {status.status.replace('_', ' ')}
                  </span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {server.enabled && (
                    <button
                      type="button"
                      className="text-xs px-2 py-1 rounded"
                      style={{
                        color: 'var(--color-cyan-light)',
                        border: '1px solid var(--color-border-subtle)',
                      }}
                      onClick={() => runHealthCheck(server.id)}
                      disabled={busy === `health:${server.id}`}
                    >
                      {busy === `health:${server.id}` ? 'Checking…' : 'Check health'}
                    </button>
                  )}
                  {/* The switch. Two labelled buttons rather than a bare toggle, so the
                      state reads in words on the control itself. */}
                  <div
                    role="group"
                    aria-label={`Computer use with ${server.id}`}
                    className="flex rounded overflow-hidden"
                    style={{ border: '1px solid var(--color-border-subtle)' }}
                  >
                    {([true, false] as const).map((on) => {
                      const active = server.enabled === on;
                      return (
                        <button
                          key={on ? 'on' : 'off'}
                          type="button"
                          data-testid={`computer-use-${on ? 'on' : 'off'}-${server.id}`}
                          aria-pressed={active}
                          disabled={busy === `toggle:${server.id}` || active}
                          onClick={() => void toggle(server.id, on)}
                          className="text-xs px-2.5 py-1"
                          style={{
                            background: active ? (on ? 'var(--color-emerald)' : 'var(--color-elevated)') : 'transparent',
                            color: active ? (on ? '#04140d' : 'var(--color-text)') : 'var(--color-text-muted)',
                            cursor: active ? 'default' : 'pointer',
                          }}
                        >
                          {on ? 'On' : 'Off'}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              <div className="text-xs font-mono truncate" style={{ color: 'var(--color-text-muted)' }}>
                {server.transport === 'http' ? server.url : server.command.join(' ')}
              </div>

              {server.knownHost && (
                <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  {server.knownHost}
                </div>
              )}

              <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                {status.detail}
              </div>

              {needsPerms && (
                <div className="flex flex-col gap-1.5 pl-3 text-xs" style={{ color: 'var(--color-amber)' }}>
                  <strong>Action required:</strong> Grant permissions in System Settings:
                  <ul className="list-disc pl-4 space-y-0.5">
                    <li>Accessibility — allows cua-driver to inspect and interact with UI elements</li>
                    <li>Screen Recording — allows cua-driver to capture window screenshots</li>
                  </ul>
                  <button
                    type="button"
                    className="self-start text-xs underline"
                    onClick={() => runHealthCheck(server.id)}
                  >
                    Re-check after granting
                  </button>
                </div>
              )}

              {!server.reachable && (
                <div className="text-xs" style={{ color: 'var(--color-amber)' }}>
                  Zaram cannot attach to this one yet — it is an HTTP server, and only
                  stdio is supported so far. It is kept so the configuration is not lost.
                </div>
              )}

              {server.grantedTools.length > 0 && (
                <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Allowed: {server.grantedTools.join(', ')}
                </div>
              )}

              {/* Quick Actions for Computer Use */}
              {server.enabled && (
              <ComputerUseAction
                serverId={server.id}
                isHealthy={isHealthy}
                busy={busy?.startsWith(`action:${server.id}`) ?? false}
                onActionComplete={reload}
              />
              )}

              {/* Tool Budget / Pinning */}
              {!server.builtin &&
              server.tools !== null &&
              server.offered !== null &&
              server.offered < server.tools && (
                <div className="flex flex-col gap-1 pl-3">
                  <button
                    type="button"
                    className="text-xs text-left"
                    style={{ color: 'var(--color-amber)' }}
                    onClick={() => loadTools(server.id)}
                    data-testid={`budget-shortfall-${server.id}`}
                  >
                    {server.tools - server.offered} of {server.tools} tools did not reach the model
                    {' '}
                    — there is room for {server.toolBudget ?? 'a few'} at once.
                    {' '}
                    Click to choose which to keep.
                  </button>
                </div>
              )}

              {server.pinnedTools.length > 0 && (
                <div className="flex flex-col gap-1 pl-3">
                  <button
                    type="button"
                    className="text-xs text-left"
                    style={{ color: 'var(--color-text-muted)' }}
                    onClick={() => loadTools(server.id)}
                    data-testid={`budget-pinned-${server.id}`}
                  >
                    Keeping {server.pinnedTools.length} tool{server.pinnedTools.length === 1 ? '' : 's'}
                    in front of the model. Click to change.
                  </button>
                </div>
              )}

              {cuatools && server.id === cuatoolsFor && (
                <div className="flex flex-col gap-1 pl-3">
                  <span className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
                    {cuatools.length} tools available:
                  </span>
                  {cuatools.map((tool) => (
                    <label
                      key={tool.name}
                      className="flex cursor-pointer items-start gap-2 text-xs"
                    >
                      <input
                        type="checkbox"
                        checked={server.pinnedTools.includes(tool.name)}
                        disabled={busy === `pin:${server.id}`}
                        onChange={() => togglePin(server.id, tool.name, server.pinnedTools)}
                        data-testid={`pin-${server.id}-${tool.name}`}
                        aria-label={`Keep ${tool.name} in front of the model`}
                      />
                      <span style={{ color: 'var(--color-text-muted)' }}>
                        <span className="font-mono">{tool.name}</span>
                        {tool.description && (
                          <span style={{ color: 'var(--color-text-faint)' }}>
                            {' — '}
                            {tool.description.slice(0, 90)}
                            {tool.description.length > 90 ? '…' : ''}
                          </span>
                        )}
                      </span>
                    </label>
                  ))}
                  <span className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
                    Keeping a tool here only means the model gets to see it. What it is
                    allowed to <em>do</em> is still asked for separately.
                  </span>
                </div>
              )}
            </div>
          );
        })}

        {/* What went wrong, said where it happened. These were set and never shown,
            so a failed install or a failed read looked like nothing having happened. */}
        {(error || loadError) && (
          <p role="alert" className="px-5 py-3 text-xs" style={{ color: 'var(--color-red)' }}>
            {error || loadError}
          </p>
        )}
      </Row>
    </>
  );
}