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
  ToolsError,
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

function ServerRow({ server, onDetach }: { server: ToolServer; onDetach: () => void }) {
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
            className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded"
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
              className="text-[11px] px-2 py-1 rounded"
              style={{ color: 'var(--color-red)', border: '1px solid var(--color-border-subtle)' }}
              onClick={onDetach}
            >
              Remove
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
            Remove
          </button>
        )}
      </div>

      <div className="text-[11px] font-mono truncate" style={{ color: 'var(--color-text-muted)' }}>
        {server.transport === 'http' ? server.url : server.command.join(' ')}
      </div>

      {/* Why it may write. The maintainer's claim, shown as one, because
          "why is this one allowed to change things" is the question a person
          has when they see the badge above. */}
      {server.knownHost && (
        <div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          {server.knownHost}
        </div>
      )}

      {/* Said plainly rather than shown as an empty tool list, which reads as a
          server that is broken rather than one this client cannot yet attach
          to. `ServerConfig.reachable` exists for exactly this. */}
      {!server.reachable && (
        <div className="text-[11px]" style={{ color: 'var(--color-amber)' }}>
          Zaram cannot attach to this one yet — it is an HTTP server, and only
          stdio is supported so far. It is kept so the configuration is not lost.
        </div>
      )}

      {server.grantedTools.length > 0 && (
        <div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          Allowed: {server.grantedTools.join(', ')}
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
        <div className="px-5 pb-2 text-[11px]" style={{ color: 'var(--color-red)' }}>
          {loadError}
        </div>
      )}

      {servers?.map((server) => (
        <ServerRow key={server.id} server={server} onDetach={() => void remove(server.id)} />
      ))}

      {servers !== null && servers.length === 0 && !adding && (
        <div className="px-5 py-3 text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
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
              className="w-full rounded-lg px-3 py-2 text-[11px] font-mono resize-y"
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
              <div role="alert" className="text-[11px]" style={{ color: 'var(--color-red)' }}>
                {formError}
              </div>
            )}
            <div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
              A pasted block cannot grant itself permission to change things.
              Whether a server may write is decided here, from a checked list of
              applications whose own undo covers what their server does.
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={busy || !block.trim()}
                onClick={() => void submit()}
                className="text-[11px] px-2.5 py-1.5 rounded"
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
                className="text-[11px] px-2.5 py-1.5 rounded"
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
            className="text-[11px] px-2.5 py-1.5 rounded"
            style={{ color: 'var(--color-text)', border: '1px solid var(--color-border-subtle)' }}
          >
            Attach a server
          </button>
        )}
      </div>
    </>
  );
}
