/**
 * The other assistants that hold Zaram's memory, and the way to add one.
 *
 * **Why this exists.** `docs/AGENT-UX.md` slice 10: Claude Code, Cline and
 * Kilo each keep a memory of their own and none of them is the user's. Zaram's
 * is — on their machine, in an open format, with provenance — so rather than
 * compete for the conversation, Zaram is the memory every one of them
 * attaches. `zaram_mcp` is the server they attach; this is where the person
 * lets one in and shows one out.
 *
 * **A token, shown once, for a minute.** The pattern is the one people learned
 * from WhatsApp: the computer shows a code, the other side redeems it, and
 * the computer can revoke it. The credential itself never appears here — the
 * client redeems the token and is the only thing that ever sees it, which is
 * what makes a stolen screenshot of this page worthless.
 *
 * **Every call a paired client makes is in Activity.** It is egress, to
 * `client:<name>`, with the bytes that left — rule 3, applied to a process
 * rather than a host. This section says so, because a person deciding whether
 * to pair should know what they will be able to see afterwards.
 *
 * Settings, not a node: tools never get menu items, and a memory client is a
 * tool pointed the other way.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  fetchPairedClients,
  issuePairingToken,
  revokePairedClient,
  type PairedClient,
  type PairingToken,
} from '../../services/pairingClient';

export interface PairingSectionProps {
  Row: React.ComponentType<{
    label: string;
    value?: string;
    detail?: React.ReactNode;
    state?: 'good' | 'neutral' | 'absent' | 'warn';
    children?: React.ReactNode;
  }>;
}

function ago(seconds: number | null): string {
  if (seconds == null) return 'never used';
  const delta = Math.max(0, Date.now() / 1000 - seconds);
  if (delta < 90) return 'used just now';
  if (delta < 3600) return `used ${Math.round(delta / 60)} min ago`;
  if (delta < 86400) return `used ${Math.round(delta / 3600)} h ago`;
  return `used ${Math.round(delta / 86400)} d ago`;
}

function ClientRow({ client, onRevoke }: { client: PairedClient; onRevoke: () => void }) {
  const [confirming, setConfirming] = useState(false);
  return (
    <div
      className="flex items-center justify-between gap-3 px-5 py-3"
      style={{ borderTop: '1px solid var(--color-border-subtle)' }}
      data-testid="paired-client"
    >
      <div className="min-w-0">
        <div
          className="text-sm truncate"
          style={{
            color: client.isActive ? 'var(--color-text)' : 'var(--color-text-muted)',
            textDecoration: client.isActive ? undefined : 'line-through',
          }}
        >
          {client.name}
        </div>
        <div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          {client.isActive
            ? `Paired ${new Date(client.linkedAt * 1000).toLocaleDateString()} · ${ago(client.lastSeen)}`
            : `Revoked ${new Date((client.revokedAt ?? 0) * 1000).toLocaleDateString()}`}
        </div>
      </div>
      {client.isActive &&
        (confirming ? (
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              className="text-[11px] px-2 py-1 rounded"
              style={{ color: 'var(--color-red)', border: '1px solid var(--color-border-subtle)' }}
              onClick={onRevoke}
            >
              Revoke
            </button>
            <button
              type="button"
              className="text-[11px] px-2 py-1 rounded"
              style={{ color: 'var(--color-text-muted)' }}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="text-[11px] px-2 py-1 rounded shrink-0"
            style={{ color: 'var(--color-text-muted)' }}
            onClick={() => setConfirming(true)}
          >
            Revoke
          </button>
        ))}
    </div>
  );
}

export default function PairingSection({ Row }: PairingSectionProps) {
  const [clients, setClients] = useState<PairedClient[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [token, setToken] = useState<PairingToken | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [issueError, setIssueError] = useState<string | null>(null);
  // The clients known when the code was issued — so "a new one appeared" is
  // an answer that does not depend on the list re-rendering underneath.
  const [knownIds, setKnownIds] = useState<Set<string>>(() => new Set());

  const reload = useCallback(async (signal?: AbortSignal) => {
    try {
      setClients(await fetchPairedClients(signal));
      setLoadError(null);
    } catch (caught) {
      if ((caught as Error).name === 'AbortError') return;
      setClients(null);
      setLoadError((caught as Error).message);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void reload(controller.signal);
    return () => controller.abort();
  }, [reload]);

  // The token's clock. When it runs out the code is gone from the screen too:
  // a code still showing after it stopped working is a code someone will
  // paste and then blame the product for. The same applies the moment it is
  // *used* — it is single-use, so while a code is showing the list is asked
  // every two seconds, and a new client appearing is what takes the code
  // down and puts the row up. Seen on screen, 13 September: without this the
  // dead code sat there for the rest of its minute after pairing had worked.
  useEffect(() => {
    if (!token) return;
    setSecondsLeft(Math.round(token.expiresIn));
    const started = Date.now();
    const known = knownIds;
    let stopped = false;
    const timer = window.setInterval(() => {
      const left = Math.round(token.expiresIn - (Date.now() - started) / 1000);
      if (left <= 0) {
        stopped = true;
        window.clearInterval(timer);
        setToken(null);
        void reload();
        return;
      }
      setSecondsLeft(left);
      if (left % 2 === 0) {
        void fetchPairedClients()
          .then((latest) => {
            if (stopped) return;
            setClients(latest);
            if (latest.some((c) => !known.has(c.id))) {
              stopped = true;
              window.clearInterval(timer);
              setToken(null);
            }
          })
          .catch(() => undefined);
      }
    }, 1000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
    // `clients` is read once, when the code is issued, to know what is new.
  }, [token, reload, knownIds]);

  const issue = useCallback(async () => {
    setIssueError(null);
    try {
      setKnownIds(new Set((clients ?? []).map((c) => c.id)));
      setToken(await issuePairingToken());
    } catch (caught) {
      setIssueError((caught as Error).message);
    }
  }, [clients]);

  const revoke = useCallback(
    async (id: string) => {
      await revokePairedClient(id);
      await reload();
    },
    [reload],
  );

  const active = (clients ?? []).filter((c) => c.isActive);
  const command = token ? token.command.replace('<token>', token.token) : '';

  return (
    <>
      <Row
        label="Other assistants"
        value={
          loadError ? 'could not ask' : clients == null ? '…' : `${active.length} paired`
        }
        state={loadError ? 'warn' : active.length > 0 ? 'good' : 'neutral'}
        detail={
          loadError ??
          'Claude Code, Cline or anything that speaks MCP can hold Zaram’s memory: ' +
            'recall, remember and correct, scoped to a project, with provenance. ' +
            'Nothing else — not the log, not the settings. Every call one makes is ' +
            'in Activity as bytes that left to that client, and a revoked client is ' +
            'refused on its next call.'
        }
      >
        {clients?.map((client) => (
          <ClientRow key={client.id} client={client} onRevoke={() => void revoke(client.id)} />
        ))}

        <div
          className="flex flex-col gap-2 px-5 py-3"
          style={{ borderTop: '1px solid var(--color-border-subtle)' }}
        >
          {token ? (
            <>
              <div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                Run this where the client lives, within {secondsLeft}s. The code works once; the
                client prints the block to paste into its MCP configuration.
              </div>
              <code
                className="text-[11px] font-mono px-2 py-1.5 rounded break-all select-all"
                style={{
                  background: 'var(--color-surface-2, rgba(127,127,127,0.08))',
                  color: 'var(--color-text)',
                }}
                data-testid="pairing-command"
              >
                {command}
              </code>
            </>
          ) : (
            <div className="flex items-center justify-between gap-3">
              <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                {issueError ?? 'Pair a new client with a one-time code.'}
              </span>
              <button
                type="button"
                className="text-[11px] px-2 py-1 rounded shrink-0"
                style={{
                  color: 'var(--color-indigo-light)',
                  border: '1px solid var(--color-border-subtle)',
                }}
                onClick={() => void issue()}
              >
                Show a pairing code
              </button>
            </div>
          )}
        </div>
      </Row>
    </>
  );
}
