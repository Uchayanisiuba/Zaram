/**
 * The model servers on this machine, and whether Zaram can reach them.
 *
 * Asked for 4 October 2026, the day a started TabbyAPI showed no Qwen in Zaram:
 * *"confirm we have access to Ollama and Tabby in the section of Settings where
 * users can download LLMs, and make Tabby always launch when it is installed."*
 *
 * **Three facts, kept apart, because the failures live in the gaps between them.**
 * A server can be *installed* and not running — one button fixes that. It can be
 * *running* and not yet seen by Zaram, which probes for models at boot and on a
 * rescan — that is what happened to the Qwen, and a rescan fixes it. Or it can be
 * running and fully seen. A single green dot would call all three the same.
 *
 * **"Zaram has them" is read from Zaram's own catalogue, not from the server.**
 * The server saying it holds a model proves the server works; it does not prove
 * Zaram can use it. That second number is the one that answers "do we have
 * access", so it is the one drawn.
 *
 * It starts nothing on its own: starting a server at launch is the backend's job
 * (`providers/model_servers.py`), and this shows what it did and lets a person
 * start one that is stopped. Loopback only; nothing here leaves the machine.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Check, Loader2, Minus } from 'lucide-react';

import {
  SettingsError,
  fetchModelServers,
  startModelServer,
  updateModelServer,
  type ModelServer,
} from '@/services/settingsClient';

/** How often to look again while a server is on its way up. TabbyAPI takes ~20 s
 *  to answer, so a few seconds keeps it feeling live without hammering. */
const POLL_MS = 2000;

/** Give up polling after this many looks. A server not answering in three
 *  minutes is reported as not responding by the backend; this only stops the
 *  page asking forever. */
const MAX_POLLS = 90;

/** What to say beside the name, in a person's words. Pure, so it can be asserted. */
export function describe(server: ModelServer): string {
  switch (server.state) {
    case 'running':
      return server.modelCount === 1 ? 'running · 1 model' : `running · ${server.modelCount} models`;
    case 'starting':
      return 'starting…';
    case 'stopped':
      return 'installed, not running';
    case 'not_installed':
      return 'not installed';
    case 'cannot_start':
      return 'installed, cannot be started';
    case 'port_taken':
      return `port ${server.port} is used by another program`;
    case 'stalled':
      return 'not responding';
    default:
      return 'unknown';
  }
}

/** Whether Zaram has what the server holds. `null` when there is nothing to say.
 *
 *  Only **zero beside a non-zero count** is called out: some of what a server
 *  lists is not something Zaram offers (an embedding model, say), so a partial
 *  count is ordinary and alarming about it would cry wolf. Having none of a
 *  server's models while it is up is not ordinary — it means Zaram has not looked
 *  since the server came up. */
export function accessNote(server: ModelServer): { text: string; warn: boolean } | null {
  if (server.state !== 'running' || server.zaramSees === null) return null;
  if (server.modelCount === 0) {
    return { text: 'Nothing is loaded in it yet, so there is nothing for Zaram to use.', warn: false };
  }
  if (server.zaramSees === 0) {
    return {
      text: 'Zaram has not picked these up yet — look for models again and they will appear.',
      warn: true,
    };
  }
  return { text: 'Zaram has them and can use them.', warn: false };
}

interface Props {
  /** Look for models again — the same action as the rest of Settings uses, so a
   *  server that just came up is picked up without a second place to press. */
  onRescan?: () => void;
}

export default function ModelServers({ onRescan }: Props) {
  const [servers, setServers] = useState<ModelServer[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [polls, setPolls] = useState(0);
  // Drafts, so a half-typed path is not sent on every keystroke. Absent means
  // "not being edited", which is not the same as the empty string.
  const [drafts, setDrafts] = useState<Record<string, { path?: string; python?: string }>>({});
  const [problems, setProblems] = useState<Record<string, string>>({});
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const next = await fetchModelServers();
      if (!mounted.current) return;
      setServers(next);
      setError(null);
    } catch (e) {
      if (!mounted.current) return;
      setError(e instanceof SettingsError ? e.message : 'Could not read the local servers.');
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => {
      mounted.current = false;
    };
  }, [refresh]);

  // Keep looking while any server is on its way up, and stop when none is.
  const anyStarting = servers?.some((s) => s.state === 'starting') ?? false;
  useEffect(() => {
    if (!anyStarting || polls >= MAX_POLLS) return;
    const timer = window.setTimeout(() => {
      setPolls((n) => n + 1);
      void refresh();
    }, POLL_MS);
    return () => window.clearTimeout(timer);
  }, [anyStarting, polls, refresh, servers]);

  const replace = (next: ModelServer) =>
    setServers((current) => (current ? current.map((s) => (s.id === next.id ? next : s)) : current));

  const start = async (server: ModelServer) => {
    setBusy(server.id);
    setPolls(0);
    try {
      replace(await startModelServer(server.id));
      setError(null);
    } catch (e) {
      setError(e instanceof SettingsError ? e.message : `Could not start ${server.label}.`);
    } finally {
      setBusy(null);
    }
  };

  const toggleAuto = async (server: ModelServer) => {
    setBusy(server.id);
    try {
      replace(await updateModelServer(server.id, { autoStart: !server.autoStart }));
    } catch (e) {
      setError(e instanceof SettingsError ? e.message : 'Could not save that.');
    } finally {
      setBusy(null);
    }
  };

  const saveLocation = async (server: ModelServer) => {
    const draft = drafts[server.id];
    if (!draft) return;
    setBusy(server.id);
    try {
      replace(
        await updateModelServer(server.id, {
          ...(draft.path !== undefined ? { path: draft.path } : {}),
          ...(draft.python !== undefined ? { python: draft.python } : {}),
        }),
      );
      setProblems((p) => ({ ...p, [server.id]: '' }));
      setDrafts((d) => {
        const { [server.id]: _gone, ...rest } = d;
        return rest;
      });
    } catch (e) {
      // The backend refuses a location that is not an install, with the reason.
      // Shown against the field it is about, not in the shared banner.
      setProblems((p) => ({ ...p, [server.id]: e instanceof SettingsError ? e.message : 'Could not save that.' }));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-2" data-testid="model-servers">
      <div className="flex items-baseline gap-2">
        <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Model servers on this machine
        </span>
        {servers && (
          <span className="text-xs" style={{ color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>
            {servers.filter((s) => s.state === 'running').length} of {servers.length} running
          </span>
        )}
      </div>

      {servers === null && !error && (
        <span className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
          looking…
        </span>
      )}

      {servers?.map((server) => {
        const note = accessNote(server);
        const running = server.state === 'running';
        const trouble = ['cannot_start', 'port_taken', 'stalled'].includes(server.state) || Boolean(server.failure);
        const colour = running
          ? note?.warn
            ? 'var(--color-amber, #fbbf24)'
            : 'var(--color-emerald)'
          : trouble
            ? 'var(--color-amber, #fbbf24)'
            : 'var(--color-text-muted)';
        const draft = drafts[server.id];
        const dirty = draft !== undefined;
        return (
          <div
            key={server.id}
            data-testid={`model-server-${server.id}`}
            className="flex items-start gap-3 rounded-lg px-3 py-2.5"
            style={{ border: '1px solid var(--color-border)' }}
          >
            <span className="mt-0.5 shrink-0" style={{ color: colour }}>
              {server.state === 'starting' ? (
                <Loader2 size={14} className="animate-spin" />
              ) : running && !note?.warn ? (
                <Check size={14} />
              ) : running || trouble ? (
                <AlertTriangle size={14} />
              ) : (
                <Minus size={14} />
              )}
            </span>

            <div className="flex-1 min-w-0 flex flex-col gap-1">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="text-sm" style={{ color: 'var(--color-text)' }}>
                  {server.label}
                </span>
                <span
                  data-testid={`model-server-state-${server.id}`}
                  className="text-xs"
                  style={{ fontFamily: 'var(--font-mono)', color: colour }}
                >
                  {describe(server)}
                </span>
              </div>

              {running && server.models.length > 0 && (
                <span
                  className="text-xs truncate"
                  style={{ color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}
                  title={server.models.join(', ')}
                >
                  {server.models.join(' · ')}
                  {server.modelCount > server.models.length ? ` · +${server.modelCount - server.models.length}` : ''}
                </span>
              )}

              {note && (
                <span
                  data-testid={`model-server-access-${server.id}`}
                  className="text-xs leading-snug"
                  style={{ color: note.warn ? 'var(--color-amber, #fbbf24)' : 'var(--color-text-faint)', maxWidth: '52ch' }}
                >
                  {note.text}
                </span>
              )}

              {server.problem && (
                <span className="text-xs leading-snug" style={{ color: 'var(--color-amber, #fbbf24)', maxWidth: '52ch' }}>
                  {server.problem}
                </span>
              )}

              {server.failure && (
                <pre
                  data-testid={`model-server-failure-${server.id}`}
                  className="text-xs overflow-auto rounded p-2"
                  style={{
                    maxHeight: 96,
                    maxWidth: '60ch',
                    margin: 0,
                    whiteSpace: 'pre-wrap',
                    color: 'var(--color-text-muted)',
                    background: 'var(--color-surface-2, rgba(255,255,255,0.04))',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {server.failure}
                </pre>
              )}

              {server.state === 'not_installed' && (
                <span className="text-xs leading-snug" style={{ color: 'var(--color-text-faint)', maxWidth: '52ch' }}>
                  Not found where Zaram looks. If you have it, say where under Advanced and Zaram
                  will start it from then on.
                </span>
              )}

              <div className="flex items-center gap-2 flex-wrap mt-0.5">
                {server.canStart && (
                  <button
                    type="button"
                    data-testid={`start-${server.id}`}
                    disabled={busy === server.id}
                    onClick={() => void start(server)}
                    className="rounded-lg px-2.5 py-1 text-xs disabled:opacity-40"
                    style={{ border: '1px solid var(--color-cyan)', color: 'var(--color-cyan-light)' }}
                  >
                    Start {server.label}
                  </button>
                )}

                {running && note?.warn && onRescan && (
                  <button
                    type="button"
                    data-testid={`rescan-${server.id}`}
                    onClick={onRescan}
                    className="rounded-lg px-2.5 py-1 text-xs"
                    style={{ border: '1px solid var(--color-cyan)', color: 'var(--color-cyan-light)' }}
                  >
                    Look for models
                  </button>
                )}

                {server.installed && (
                  <button
                    type="button"
                    role="switch"
                    aria-checked={server.autoStart}
                    data-testid={`auto-start-${server.id}`}
                    disabled={busy === server.id}
                    onClick={() => void toggleAuto(server)}
                    className="rounded-lg px-2.5 py-1 text-xs disabled:opacity-40"
                    style={{
                      border: `1px solid ${server.autoStart ? 'var(--color-cyan)' : 'var(--color-border)'}`,
                      color: server.autoStart ? 'var(--color-cyan-light)' : 'var(--color-text-muted)',
                    }}
                  >
                    {server.autoStart ? 'Starts with Zaram' : 'Does not start with Zaram'}
                  </button>
                )}
              </div>

              <details className="mt-0.5" data-testid={`model-server-advanced-${server.id}`}>
                <summary className="text-xs cursor-pointer select-none" style={{ color: 'var(--color-text-muted)' }}>
                  Advanced
                </summary>
                <div className="flex flex-col gap-2 mt-2">
                  {server.fields.includes('path') && (
                    <label className="flex flex-col gap-1">
                      <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                        Where {server.label} is installed
                      </span>
                      <input
                        data-testid={`path-${server.id}`}
                        value={draft?.path ?? server.path ?? ''}
                        placeholder="Leave empty and Zaram looks"
                        onChange={(e) => setDrafts((d) => ({ ...d, [server.id]: { ...d[server.id], path: e.target.value } }))}
                        className="rounded-lg px-2.5 py-1.5 text-xs"
                        style={{
                          background: 'transparent',
                          border: '1px solid var(--color-border)',
                          color: 'var(--color-text)',
                          fontFamily: 'var(--font-mono)',
                          maxWidth: '60ch',
                        }}
                      />
                    </label>
                  )}
                  {server.fields.includes('python') && (
                    <label className="flex flex-col gap-1">
                      <span className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                        Python to run it with
                      </span>
                      <input
                        data-testid={`python-${server.id}`}
                        value={draft?.python ?? ''}
                        placeholder="Leave empty and Zaram looks beside it"
                        onChange={(e) => setDrafts((d) => ({ ...d, [server.id]: { ...d[server.id], python: e.target.value } }))}
                        className="rounded-lg px-2.5 py-1.5 text-xs"
                        style={{
                          background: 'transparent',
                          border: '1px solid var(--color-border)',
                          color: 'var(--color-text)',
                          fontFamily: 'var(--font-mono)',
                          maxWidth: '60ch',
                        }}
                      />
                    </label>
                  )}
                  {problems[server.id] && (
                    <span
                      data-testid={`location-problem-${server.id}`}
                      className="text-xs leading-snug"
                      style={{ color: 'var(--color-amber, #fbbf24)', maxWidth: '52ch' }}
                    >
                      {problems[server.id]}
                    </span>
                  )}
                  {dirty && (
                    <div>
                      <button
                        type="button"
                        data-testid={`save-location-${server.id}`}
                        disabled={busy === server.id}
                        onClick={() => void saveLocation(server)}
                        className="rounded-lg px-2.5 py-1 text-xs disabled:opacity-40"
                        style={{ border: '1px solid var(--color-cyan)', color: 'var(--color-cyan-light)' }}
                      >
                        Save
                      </button>
                    </div>
                  )}
                </div>
              </details>
            </div>
          </div>
        );
      })}

      {error && (
        <span data-testid="model-servers-error" className="text-xs" style={{ color: 'var(--color-amber, #fbbf24)' }}>
          {error}
        </span>
      )}
    </div>
  );
}
