/**
 * Report a problem — the one feedback channel, and it travels with the person.
 *
 * Zaram sends nothing on its own (rule 7g) and has no thumbs (rule 7f). So a
 * problem is reported the way anything leaves this machine: the person sees
 * the exact text, copies it, and pastes it where they already talk to the
 * maintainer — a reply to the tester email, or a GitHub issue. The backend
 * writes the report (`core/report.py`) and says at its top what it holds and
 * what it does not: no conversation, no document names, no facts, no keys.
 *
 * Takes `Row` as a prop, as `ToolsSection` does, so this file and the
 * workspace do not import each other in a circle.
 */

import { useCallback, useState } from 'react';

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export const ISSUES_URL = 'https://github.com/Uchayanisiuba/Zaram/issues/new';
/** The feedback form on the site — no account needed, same form host as the
 *  signup. The report is copied first, so the person has it to paste. */
export const FEEDBACK_URL = 'https://uchayanisiuba.github.io/Zaram/#feedback';

/** Open a page in the system browser.
 *
 *  Found 20 September 2026: the GitHub link here was a plain `<a
 *  target="_blank">`, and the packaged app's `hardenWindow` denies every
 *  window-open and off-app navigation — so on the one screen a tester in
 *  trouble reaches, the link did nothing. The shell bridge is the route; a
 *  plain browser tab during development falls back to `window.open`. */
export function openInBrowser(url: string): void {
  const shell = window.zaram?.shell?.openExternal;
  if (typeof shell === 'function') {
    void shell(url);
    return;
  }
  window.open(url, '_blank', 'noopener,noreferrer');
}

export interface ReportSectionProps {
  Row: React.ComponentType<{
    label: string;
    value?: string;
    detail?: React.ReactNode;
    state?: 'good' | 'neutral' | 'absent' | 'warn';
    children?: React.ReactNode;
  }>;
  /** Overrides the fetch, for tests. */
  load?: () => Promise<string>;
  /** Overrides the clipboard, for tests. */
  copy?: (text: string) => Promise<void>;
}

async function fetchReport(): Promise<string> {
  const res = await fetch(`${API_BASE}/diagnostics/report`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const body: { text?: string } = await res.json();
  return body.text ?? '';
}

async function toClipboard(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}

export default function ReportSection({ Row, load = fetchReport, copy = toClipboard }: ReportSectionProps) {
  const [text, setText] = useState<string | null>(null);
  const [shown, setShown] = useState(false);
  const [state, setState] = useState<'idle' | 'busy' | 'copied' | 'failed'>('idle');
  const [error, setError] = useState<string | null>(null);

  const prepare = useCallback(async () => {
    setState('busy');
    setError(null);
    try {
      const report = await load();
      setText(report);
      await copy(report);
      setState('copied');
    } catch (e) {
      setState('failed');
      setError(e instanceof Error ? e.message : 'Could not build the report.');
    }
  }, [load, copy]);

  return (
    <Row
      label="Report a problem"
      value={state === 'copied' ? 'copied' : undefined}
      state={state === 'copied' ? 'good' : state === 'failed' ? 'warn' : 'neutral'}
      detail={
        <>
          Copies a short report to your clipboard: version, hardware, the models found, your
          routing choices, and the last few things that left this machine, without their
          contents. No conversation, no document names, no remembered facts, no keys. Then
          paste it into the feedback form — no account needed — or into a reply to the
          tester email, or an issue at{' '}
          <button
            type="button"
            onClick={() => openInBrowser(ISSUES_URL)}
            style={{ color: 'var(--color-indigo-light)' }}
            data-testid="report-issues"
          >
            github.com/Uchayanisiuba/Zaram/issues
          </button>
          , with what you expected and what happened instead. Zaram sends nothing itself;
          the form is a page in your browser.
        </>
      }
    >
      <div className="flex flex-col items-end gap-2">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={prepare}
            disabled={state === 'busy'}
            className="text-xs px-3 py-1.5 rounded-lg surface"
            style={{ color: 'var(--color-text)' }}
            data-testid="report-copy"
          >
            {state === 'busy' ? 'Preparing…' : state === 'copied' ? 'Copied — copy again' : 'Copy report'}
          </button>
          <button
            type="button"
            onClick={() => openInBrowser(FEEDBACK_URL)}
            className="text-xs px-3 py-1.5 rounded-lg"
            style={{ color: 'var(--color-indigo-light)' }}
            data-testid="report-feedback"
          >
            Send feedback
          </button>
          {text && (
            <button
              type="button"
              onClick={() => setShown((s) => !s)}
              className="text-xs px-3 py-1.5 rounded-lg"
              style={{ color: 'var(--color-text-muted)' }}
              data-testid="report-toggle"
            >
              {shown ? 'Hide' : 'Show what was copied'}
            </button>
          )}
        </div>
        {error && (
          <span className="text-xs" style={{ color: 'var(--color-amber, #fbbf24)' }}>
            {error}
          </span>
        )}
        {shown && text && (
          <pre
            className="text-xs whitespace-pre-wrap max-w-xl max-h-64 overflow-auto p-3 rounded-lg"
            style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)', background: 'rgba(0,0,0,0.25)' }}
            data-testid="report-text"
          >
            {text}
          </pre>
        )}
      </div>
    </Row>
  );
}
