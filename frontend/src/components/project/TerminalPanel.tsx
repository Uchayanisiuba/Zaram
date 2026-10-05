/**
 * A terminal you can see, and type in.
 *
 * Asked for 3 October 2026 (*"does Zaram have a terminal like yours"*) and built
 * as tools the same day. The tools' own header names the condition that makes
 * them acceptable: **the person sees every command and can type their own.** A
 * shell Zaram can drive and its owner cannot watch is a hidden subprocess, so
 * this is the half that was owed.
 *
 * What it shows is the project's one shell -- what Zaram ran and what you ran,
 * in order, each line labelled with who caused it. It is not a PTY: there is no
 * colour, no cursor movement and no `vim`, and it says so rather than letting
 * somebody discover it. The jobs it exists for (a virtualenv, an install, a
 * scaffold, a build) are non-interactive.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, Square, TerminalSquare } from 'lucide-react';

import {
  readTerminal,
  stopTerminal,
  typeInTerminal,
  type TerminalLine,
} from '@/services/terminalClient';

/** How often the scrollback is re-read while the panel is open. A command that
 *  takes minutes shows its output as it arrives; one that has finished costs a
 *  small local request per interval and nothing leaves the machine. */
const POLL_MS = 1500;

interface Props {
  projectId: string;
}

export default function TerminalPanel({ projectId }: Props) {
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [cwd, setCwd] = useState('');
  const [draft, setDraft] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const bottom = useRef<HTMLDivElement | null>(null);

  const refresh = useCallback(async () => {
    try {
      const state = await readTerminal(projectId);
      setLines(state.lines);
      setCwd(state.cwd);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not read the terminal.');
    }
  }, [projectId]);

  useEffect(() => {
    if (!open) return undefined;
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, [open, refresh]);

  // Follow the output, the way a terminal does.
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: 'end' });
  }, [lines]);

  async function submit() {
    const command = draft.trim();
    if (!command || running) return;
    setDraft('');
    setRunning(true);
    setError('');
    try {
      const state = await typeInTerminal(projectId, command);
      setLines(state.lines);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That command could not be run.');
    } finally {
      setRunning(false);
    }
  }

  async function stop() {
    try {
      await stopTerminal(projectId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not close the terminal.');
    }
  }

  return (
    <div className="pl-6" data-testid="terminal-panel">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((was) => !was)}
        className="flex items-center gap-1.5 text-xs underline-offset-2 hover:underline"
        style={{ color: 'var(--color-cyan-light)' }}
      >
        <TerminalSquare size={13} aria-hidden />
        {open ? 'Hide the terminal' : 'Open the terminal'}
      </button>

      {open && (
        <div
          className="mt-2 flex flex-col overflow-hidden rounded-lg"
          style={{ border: '1px solid var(--color-border)', background: 'rgba(0,0,0,0.35)' }}
        >
          <div
            data-testid="terminal-lines"
            className="max-h-64 min-h-24 overflow-auto px-3 py-2 text-xs leading-relaxed"
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {lines.length === 0 && (
              <span style={{ color: 'var(--color-text-faint)' }}>
                Nothing has been run yet. What Zaram runs here shows up too, labelled.
              </span>
            )}
            {lines.map((line, index) =>
              line.kind === 'command' ? (
                <div key={index} data-testid="terminal-command" className="flex gap-2">
                  <span
                    className="shrink-0"
                    style={{
                      color: line.who === 'user' ? 'var(--color-emerald)' : 'var(--color-cyan-light)',
                    }}
                  >
                    {line.who === 'user' ? 'you' : 'zaram'}
                  </span>
                  <span style={{ color: 'var(--color-text)' }}>$ {line.text}</span>
                </div>
              ) : (
                <div
                  key={index}
                  className="whitespace-pre-wrap pl-12"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {line.text}
                </div>
              ),
            )}
            <div ref={bottom} />
          </div>

          <form
            className="flex items-center gap-2 px-3 py-2"
            style={{ borderTop: '1px solid var(--color-border-subtle)' }}
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            <span className="text-xs" style={{ color: 'var(--color-emerald)', fontFamily: 'var(--font-mono)' }}>
              $
            </span>
            <input
              data-testid="terminal-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={running}
              spellCheck={false}
              autoComplete="off"
              aria-label="A command to run in this project's terminal"
              placeholder={running ? 'Running…' : 'Type a command'}
              className="min-w-0 flex-1 bg-transparent text-xs outline-none disabled:opacity-60"
              style={{ color: 'var(--color-text)', fontFamily: 'var(--font-mono)' }}
            />
            {running && <Loader2 size={13} className="animate-spin" aria-hidden />}
            <button
              type="button"
              onClick={() => void stop()}
              aria-label="Close the terminal and stop whatever is running"
              title="Close the terminal and stop whatever is running"
              className="rounded p-1"
              style={{ color: 'var(--color-text-faint)' }}
            >
              <Square size={12} aria-hidden />
            </button>
          </form>

          {error && (
            <p
              data-testid="terminal-error"
              className="px-3 pb-2 text-xs"
              style={{ color: 'var(--color-amber-light, #fcd34d)' }}
            >
              {error}
            </p>
          )}

          <p className="px-3 pb-2 text-xs leading-snug" style={{ color: 'var(--color-text-faint)' }}>
            {cwd && <>In {cwd}. </>}
            Not a full terminal: no colour, no cursor movement, nothing interactive like vim. It is
            for setting a project up — an environment, an install, a build. What you type here is
            yours and is not asked about; what Zaram runs is labelled and a push is asked about first.
          </p>
        </div>
      )}
    </div>
  );
}
