/**
 * The MCP servers this machine has, and what each of them may do.
 *
 * **This is the way in that was missing, not a new capability.** The client has
 * been live since 1 September — `core/bootstrapper.py` builds the runtime,
 * `core/planner.py` can name `mcp.call`, `core/execution_engine.py` runs it —
 * and attaching a server meant hand-editing `mcp-servers.json` in the data
 * directory. Seven servers were configured on the maintainer's machine and
 * nothing in the product could show them.
 *
 * **Settings is where tools are configured, and they never get a menu item.**
 * `CLAUDE.md` is explicit: *tools never get menu items; they are actions inside
 * the conversation. This is what lets capability grow without the navigation
 * growing.* So this is a section here, and the tools themselves stay in chat.
 *
 * **Paste, do not fill in a form.** The format matches `.mcp.json` so a server
 * working in another client is pasted rather than retyped. A form would be a
 * second config format, which is the plugin-format mistake arriving by the back
 * door.
 *
 * **Write permission is shown, never offered here.** `runtimes/mcp/api.py`
 * strips `writes` from anything pasted, and the mode comes from the
 * maintainer's own checked list of applications whose undo actually covers what
 * their server does. A control here that raised it would hand the decision back
 * to whoever wrote the block — so there isn't one, and the reason is displayed
 * instead.
 *
 * Lives in its own file because `SettingsWorkspace` is already over 1,500 lines,
 * and takes `Row` as a prop rather than importing it, so the two files do not
 * import each other in a circle.
 */

import { useCallback, useEffect, useState } from 'react';
import {
  attachServers,
  detachServer,
  fetchServers,
  fetchServerTools,
  pinTools,
  ToolsError,
  type ServerTool,
  type ToolServer,
} from '../../services/toolsClient';

export interface ToolsSectionProps {
  /** `Row` from `SettingsWorkspace`, passed in so this file does not import
   *  from the workspace that renders it. */
  Row: React.ComponentType<{
    label: string;
    value?: string;
    detail?: React.ReactNode;
    state?: 'good' | 'neutral' | 'absent' | 'warn';
    children?: React.ReactNode;
  }>;
}

const PLACEHOLDER = `{
  "mcpServers": {
    "blender": {
      "command": "uvx",
      "args": ["blender-mcp"]
    }
  }
}`;

/** What the server is allowed to change, in words rather than a mode string.
 *
 *  `read_only` is deliberately not phrased as a limitation: it is the default
 *  and the safe answer, and a person scanning this list should not read the
 *  correct state as a problem to fix. */
function writesLabel(server: ToolServer): string {
  return server.writes === 'host_undo' ? 'Can change things' : 'Reads only';
}

function ServerRow({
  server,
  onDetach,
  onPinned,
}: {
  server: ToolServer;
  onDetach: () => void;
  /** Reload the list, so the pin that was just set is the one on screen.
   *  The counts come from the backend and a local guess at them would be the
   *  invented value `CLAUDE.md` calls worse than no indicator. */
  onPinned: () => void;
}) {
  const [confirming, setConfirming] = useState(false);

  return (
    <div
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
                server.writes === 'host_undo' ? 'var(--color-amber)' : 'var(--color-text-muted)',
              border: '1px solid var(--color-border-subtle)',
            }}
          >
            {writesLabel(server)}
          </span>
        </div>

        {confirming ? (
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              className="text-xs px-2 py-1 rounded"
              style={{ color: 'var(--color-red)', border: '1px solid var(--color-border-subtle)' }}
              onClick={onDetach}
            >
              Remove
            </button>
            <button
              type="button"
              className="text-xs px-2 py-1 rounded"
              style={{ color: 'var(--color-text-muted)' }}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="text-xs px-2 py-1 rounded shrink-0"
            style={{ color: 'var(--color-text-muted)' }}
            onClick={() => setConfirming(true)}
          >
            Remove
          </button>
        )}
      </div>

      <div className="text-xs font-mono truncate" style={{ color: 'var(--color-text-muted)' }}>
        {server.transport === 'http' ? server.url : server.command.join(' ')}
      </div>

      {/* Why it may write. The maintainer's claim, shown as one, because
          "why is this one allowed to change things" is the question a person
          has when they see the badge above. */}
      {server.knownHost && (
        <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
          {server.knownHost}
        </div>
      )}

      {/* Said plainly rather than shown as an empty tool list, which reads as a
          server that is broken rather than one this client cannot yet attach
          to. `ServerConfig.reachable` exists for exactly this. */}
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

      <ToolBudgetRow server={server} onPinned={onPinned} />
    </div>
  );
}

/**
 * What the context budget dropped, and which tools to keep instead.
 *
 * **The numbers existed for a fortnight with no caller.** The runtime has
 * recorded how many tools each server offers and how many survived the budget
 * since 20 September, on `/tools/health`, and nothing in the interface ever
 * asked. So attaching a 39-tool server — Comfy Org's `comfy-mcp` is one —
 * showed 8 and said nothing about the other 31, and the model then truthfully
 * reported that it could not do the thing while the server sat there healthy.
 * `CLAUDE.md`: *a disabled capability is visible, not silent.* Exactly the
 * base rate that file names — complete, tested, unreachable.
 *
 * **Saying it is only half.** A product that reports "31 tools omitted" and
 * offers no way to choose which is a complaint rather than a control, the same
 * way a refusal that does not name the switch reads as a broken product. So
 * the sentence opens a list, and a pin keeps that tool in front of the model
 * whatever the budget would otherwise do.
 *
 * **A pin is visibility, never permission.** Being seen by the model is not
 * being allowed to act; the risk tier and the grant still decide that, and
 * they are a different field. A control that quietly granted what it revealed
 * would turn the budget into a permission surface.
 */
function ToolBudgetRow({
  server,
  onPinned,
}: {
  server: ToolServer;
  onPinned: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [names, setNames] = useState<ServerTool[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Zaram's own packs are never trimmed, so a built-in is not short of
  // anything and must not carry a warning about it.
  const short =
    !server.builtin &&
    server.tools !== null &&
    server.offered !== null &&
    server.offered < server.tools;

  const load = useCallback(async () => {
    setError(null);
    try {
      setNames(await fetchServerTools(server.id));
    } catch (caught) {
      // Never an empty list on a failed fetch: "this server offers nothing"
      // and "Zaram could not ask" are different answers.
      setNames(null);
      setError((caught as Error).message);
    }
  }, [server.id]);

  const toggleOpen = useCallback(() => {
    setOpen((was) => !was);
    if (!open && names === null) void load();
  }, [open, names, load]);

  const togglePin = useCallback(
    async (name: string) => {
      if (busy) return;
      setBusy(true);
      const next = server.pinnedTools.includes(name)
        ? server.pinnedTools.filter((n) => n !== name)
        : [...server.pinnedTools, name];
      try {
        await pinTools(server.id, next);
        onPinned();
      } catch (caught) {
        setError((caught as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [busy, server.id, server.pinnedTools, onPinned],
  );

  // Nothing to say: no question has gone through yet, or every tool fits.
  // `null` is deliberately not 0 here — see `ToolServer.tools`.
  if (!short && server.pinnedTools.length === 0) return null;

  const omitted =
    server.tools !== null && server.offered !== null ? server.tools - server.offered : 0;

  return (
    <div className="flex flex-col gap-1">
      {short && (
        <button
          type="button"
          className="text-xs text-left"
          style={{ color: 'var(--color-amber)' }}
          onClick={toggleOpen}
          data-testid={`budget-shortfall-${server.id}`}
        >
          {omitted} of {server.tools} tools did not reach the model — there is
          room for {server.toolBudget ?? 'a few'} at once, shared with every
          other attached server.
          {server.pinnedTools.length > 0
            ? ` You are keeping ${server.pinnedTools.length} of them. `
            : ' '}
          {open ? 'Hide' : 'Choose which to keep'}
        </button>
      )}

      {!short && server.pinnedTools.length > 0 && (
        <button
          type="button"
          className="text-xs text-left"
          style={{ color: 'var(--color-text-muted)' }}
          onClick={toggleOpen}
          data-testid={`budget-pinned-${server.id}`}
        >
          Keeping {server.pinnedTools.length} tool
          {server.pinnedTools.length === 1 ? '' : 's'} in front of the model.{' '}
          {open ? 'Hide' : 'Change'}
        </button>
      )}

      {open && (
        <div className="flex flex-col gap-1 pl-3">
          {error && (
            <span className="text-xs" style={{ color: 'var(--color-red)' }}>
              {error}
            </span>
          )}
          {!error && names === null && (
            <span className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
              Asking the server what it offers…
            </span>
          )}
          {names?.map((tool) => (
            <label
              key={tool.name}
              className="flex cursor-pointer items-start gap-2 text-xs"
            >
              <input
                type="checkbox"
                checked={server.pinnedTools.includes(tool.name)}
                disabled={busy}
                onChange={() => void togglePin(tool.name)}
                data-testid={`pin-${server.id}-${tool.name}`}
                aria-label={`Keep ${tool.name} in front of the model`}
              />
              <span style={{ color: 'var(--color-text-muted)' }}>
                <span className="font-mono">{tool.name}</span>
                {tool.description && (
                  /* The server author's own words, carried rather than
                     paraphrased — and third-party text, which is why nothing
                     here renders it as markup. */
                  <span style={{ color: 'var(--color-text-faint)' }}>
                    {' — '}
                    {tool.description.slice(0, 90)}
                    {tool.description.length > 90 ? '…' : ''}
                  </span>
                )}
              </span>
            </label>
          ))}
          {names?.length === 0 && !error && (
            <span className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
              This server listed no tools.
            </span>
          )}
          <span className="text-xs" style={{ color: 'var(--color-text-faint)' }}>
            Keeping a tool here only means the model gets to see it. What it is
            allowed to <em>do</em> is still asked for separately.
          </span>
        </div>
      )}
    </div>
  );
}

export default function ToolsSection({ Row }: ToolsSectionProps) {
  const [servers, setServers] = useState<ToolServer[] | null>(null);
  // Two error slots, because they are two different failures and they belong in
  // two different places. Reading the list can fail before anything is on
  // screen; a paste fails while the person is looking at the box they pasted
  // into. Sharing one slot put "that is not valid JSON" at the top of the
  // section with seven servers between it and the textarea -- found by opening
  // the page and clicking Attach on a broken block, which is the only way that
  // kind of mistake shows up.
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [block, setBlock] = useState('');
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async (signal?: AbortSignal) => {
    try {
      setServers(await fetchServers(signal));
      setLoadError(null);
    } catch (caught) {
      if ((caught as Error).name === 'AbortError') return;
      // Never render an empty list on a failed fetch: "no servers" and "could
      // not ask" are different answers and only one of them is the user's
      // problem to act on.
      setServers(null);
      setLoadError((caught as Error).message);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void reload(controller.signal);
    return () => controller.abort();
  }, [reload]);

  const submit = useCallback(async () => {
    setBusy(true);
    setFormError(null);
    try {
      await attachServers(block);
      setBlock('');
      setAdding(false);
      await reload();
    } catch (caught) {
      const message =
        caught instanceof ToolsError ? caught.message : (caught as Error).message;
      setFormError(message);
    } finally {
      setBusy(false);
    }
  }, [block, reload]);

  const remove = useCallback(
    async (serverId: string) => {
      setBusy(true);
      try {
        await detachServer(serverId);
        await reload();
      } catch (caught) {
        // A failed removal belongs with the list, not with the paste box.
        setLoadError((caught as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [reload],
  );

  const count = servers?.length ?? 0;

  return (
    <>
      <Row
        label="Tool servers"
        value={servers === null ? 'unknown' : count === 0 ? 'none' : `${count} attached`}
        state={servers === null ? 'warn' : count === 0 ? 'absent' : 'neutral'}
        detail={
          <span>
            Any MCP server can be attached. Zaram maintains none of them, and a
            server nobody has vouched for can only read.
          </span>
        }
      />

      {loadError && (
        <div className="px-5 pb-2 text-xs" style={{ color: 'var(--color-red)' }}>
          {loadError}
        </div>
      )}

      {servers?.map((server) => (
        <ServerRow
          key={server.id}
          server={server}
          onDetach={() => void remove(server.id)}
          onPinned={() => void reload()}
        />
      ))}

      {servers !== null && servers.length === 0 && !adding && (
        <div className="px-5 py-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          Nothing attached. A server you already use elsewhere can be pasted in
          as-is — the format is the same one every other client reads.
        </div>
      )}

      <div className="px-5 py-3" style={{ borderTop: '1px solid var(--color-border-subtle)' }}>
        {adding ? (
          <div className="flex flex-col gap-2">
            <textarea
              value={block}
              onChange={(e) => setBlock(e.target.value)}
              placeholder={PLACEHOLDER}
              spellCheck={false}
              rows={8}
              aria-label="Server configuration to paste"
              className="w-full rounded-lg px-3 py-2 text-xs font-mono resize-y"
              style={{
                background: 'var(--color-glass)',
                border: '1px solid var(--color-border-subtle)',
                color: 'var(--color-text)',
              }}
            />
            {/* Beside the box, which is the whole reason the JSON is parsed
                here rather than on the server: someone mid-paste needs to know
                which bracket, and needs to read it without scrolling. */}
            {formError && (
              <div role="alert" className="text-xs" style={{ color: 'var(--color-red)' }}>
                {formError}
              </div>
            )}
            <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              A pasted block cannot grant itself permission to change things.
              Whether a server may write is decided here, from a checked list of
              applications whose own undo covers what their server does.
            </div>
            {/* **The limit, said plainly, because it is real.** `CLAUDE.md`:
                *never claim absolute security; state what is verifiable.* An
                attached server is a separate program with its own sockets, so
                `EgressGate` — which intercepts what Zaram sends — cannot see
                a request the server makes on its own. Saying "every byte is
                logged" here would be the one claim the product cannot keep.
                Zaram asks every server not to phone home (`DO_NOT_TRACK` and
                the vendor-specific opt-outs, in `child_env.py`), which is a
                request that most embedded analytics honour and none of them
                is obliged to. Blocking it properly needs an outbound firewall
                rule per child, which needs administrator rights, breaks every
                server that legitimately fetches something, and fails *open*
                when it cannot be applied — a guard that silently does nothing
                is worse than a limit somebody can read. */}
            <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
              A server runs as its own program. Zaram logs every call it makes{' '}
              <em>into</em> one, and asks each not to send usage data of its
              own — but it cannot log what another program sends. Attach
              servers you would run anyway.
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={busy || !block.trim()}
                onClick={() => void submit()}
                className="text-xs px-2.5 py-1.5 rounded"
                style={{
                  color: 'var(--color-text)',
                  border: '1px solid var(--color-border-subtle)',
                  opacity: busy || !block.trim() ? 0.5 : 1,
                }}
              >
                {busy ? 'Attaching…' : 'Attach'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setAdding(false);
                  setBlock('');
                  setFormError(null);
                }}
                className="text-xs px-2.5 py-1.5 rounded"
                style={{ color: 'var(--color-text-muted)' }}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="text-xs px-2.5 py-1.5 rounded"
            style={{ color: 'var(--color-text)', border: '1px solid var(--color-border-subtle)' }}
          >
            Attach a server
          </button>
        )}
      </div>
    </>
  );
}
