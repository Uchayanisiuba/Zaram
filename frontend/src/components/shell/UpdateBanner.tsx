/**
 * The one card about updates: the question once, and then only what is true now.
 *
 * Rule 7g, as amended 16 August 2026, says update checks are asked for once and
 * default to yes -- and nothing in the product asked. This is the asking. It says
 * what the check is made of in the same sentence as the question (an anonymous
 * request for the list of releases, nothing about the person, written to Activity
 * like any other), because a consent that does not say what it consents to is not
 * the one the rule means.
 *
 * After the answer it is quiet until there is something to act on: a newer build,
 * a download in progress, a download ready to run, or a failure. "Later" puts it
 * away for the session and nothing else -- a banner that nagged would be an
 * engagement mechanic, which this product does not have, so it does not come back
 * until the next launch and is never louder than a corner of the screen.
 *
 * **Nothing here starts a download or an install on its own.** The size is on the
 * button, and *Restart and install* says Zaram will close.
 *
 * Mounted once in the shell. Renders nothing in a build that cannot tell which
 * release it is (a development run), where there is nothing to compare against.
 */
import { useEffect } from 'react';

import { openInBrowser } from '@/lib/openInBrowser';
import { useUpdateStore } from '@/stores/updateStore';

const MIB = 1024 * 1024;

export function sizeOf(bytes: number): string {
  return bytes >= 1024 * MIB ? `${(bytes / (1024 * MIB)).toFixed(1)} GB` : `${Math.round(bytes / MIB)} MB`;
}

const BUTTON = 'rounded-lg px-3 py-1.5 text-xs disabled:opacity-40';
const PRIMARY = { border: '1px solid var(--color-cyan)', color: 'var(--color-cyan-light)' } as const;
const QUIET = { border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' } as const;

export default function UpdateBanner() {
  const { status, message, busy, dismissed, start, answer, download, install, check, dismiss } = useUpdateStore();

  useEffect(() => {
    void start();
  }, [start]);

  if (!status || !status.known) return null;

  let body: React.ReactNode = null;

  if (status.checks === null) {
    body = (
      <>
        <p data-testid="update-ask" className="text-sm" style={{ color: 'var(--color-text)' }}>
          Check for a newer Zaram when it opens?
        </p>
        <p className="mt-1 text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
          It asks GitHub for the list of releases and sends nothing about you or your work; the request is written to
          Activity like anything else that leaves. You can change this in Settings.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" data-testid="update-yes" disabled={busy} onClick={() => void answer(true)} className={BUTTON} style={PRIMARY}>
            Yes, check
          </button>
          <button type="button" data-testid="update-no" disabled={busy} onClick={() => void answer(false)} className={BUTTON} style={QUIET}>
            No thanks
          </button>
        </div>
      </>
    );
  } else if (dismissed) {
    return null;
  } else if (status.phase === 'downloading') {
    const { done, total } = status.progress;
    const percent = total > 0 ? Math.min(100, Math.floor((done / total) * 100)) : null;
    body = (
      <>
        <p className="text-sm" style={{ color: 'var(--color-text)' }}>
          Downloading {status.latest?.tag ?? 'the update'}
          {percent !== null ? ` — ${percent}%` : '…'}
        </p>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent ?? undefined}
          className="mt-2 h-1.5 w-full overflow-hidden rounded-full"
          style={{ background: 'rgba(255,255,255,0.08)' }}
        >
          <div className="h-full" style={{ width: `${percent ?? 5}%`, background: 'var(--color-cyan)' }} />
        </div>
      </>
    );
  } else if (status.ready && status.latest) {
    body = (
      <>
        <p className="text-sm" style={{ color: 'var(--color-text)' }}>
          {status.latest.tag} is ready.
        </p>
        <p className="mt-1 text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
          {status.can_install
            ? 'Zaram will close, update and open again. Your memory and settings are kept.'
            : status.manual_reason}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {status.can_install ? (
            <button type="button" data-testid="update-install" disabled={busy} onClick={() => void install()} className={BUTTON} style={PRIMARY}>
              Restart and install
            </button>
          ) : (
            <button type="button" data-testid="update-page" onClick={() => openInBrowser(status.latest!.page)} className={BUTTON} style={PRIMARY}>
              Open the release page
            </button>
          )}
          <button type="button" data-testid="update-later" onClick={dismiss} className={BUTTON} style={QUIET}>
            Later
          </button>
        </div>
      </>
    );
  } else if (status.latest && status.phase === 'available') {
    body = (
      <>
        <p data-testid="update-available" className="text-sm" style={{ color: 'var(--color-text)' }}>
          {status.latest.tag} is available.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {status.can_install ? (
            <button type="button" data-testid="update-download" disabled={busy} onClick={() => void download()} className={BUTTON} style={PRIMARY}>
              Download {sizeOf(status.latest.installer.size)}
            </button>
          ) : (
            <button type="button" data-testid="update-page" onClick={() => openInBrowser(status.latest!.page)} className={BUTTON} style={PRIMARY}>
              Open the release page
            </button>
          )}
          <button type="button" data-testid="update-notes" onClick={() => openInBrowser(status.latest!.page)} className={BUTTON} style={QUIET}>
            What’s new
          </button>
          <button type="button" data-testid="update-later" onClick={dismiss} className={BUTTON} style={QUIET}>
            Later
          </button>
        </div>
      </>
    );
  }

  // A failure with nothing else to show: said once, with the way to try again.
  if (!body && message && status.checks === true) {
    body = (
      <>
        <p data-testid="update-error" className="text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
          {message}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" data-testid="update-retry" disabled={busy} onClick={() => void check()} className={BUTTON} style={PRIMARY}>
            Try again
          </button>
          <button type="button" data-testid="update-later" onClick={dismiss} className={BUTTON} style={QUIET}>
            Dismiss
          </button>
        </div>
      </>
    );
  }

  if (!body) return null;

  return (
    <div
      role="status"
      data-testid="update-banner"
      className="fixed bottom-4 right-4 z-50 w-80 rounded-xl px-4 py-3"
      style={{ background: 'var(--color-glass)', border: '1px solid var(--color-border)', backdropFilter: 'blur(12px)' }}
    >
      {body}
      {message && status.checks !== null && body && (status.phase === 'available' || status.ready) && (
        <p className="mt-2 text-xs leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
          {message}
        </p>
      )}
    </div>
  );
}
