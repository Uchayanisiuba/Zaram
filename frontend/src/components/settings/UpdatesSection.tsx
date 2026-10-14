/**
 * Updates — which version this is, whether Zaram looks for a newer one, and the
 * same controls the banner offers.
 *
 * The switch is rule 7g's answer, changeable: on by default after the one
 * question the banner asks, and off means nothing is fetched unless the person
 * presses *Check now*. What a check sends is said here in full, because this is
 * where somebody reads it a second time.
 *
 * Shares `useUpdateStore` with the banner, so a download started in one shows its
 * progress in the other.
 */
import { useEffect } from 'react';

import { openInBrowser } from '@/lib/openInBrowser';
import { useUpdateStore } from '@/stores/updateStore';
import { sizeOf } from '@/components/shell/UpdateBanner';

export interface UpdatesSectionProps {
  Row: React.ComponentType<{
    label: string;
    value?: string;
    detail?: React.ReactNode;
    state?: 'good' | 'neutral' | 'absent' | 'warn';
    children?: React.ReactNode;
  }>;
}

const BUTTON =
  'px-3 py-1.5 rounded-md text-xs border border-slate-700/60 text-slate-200 hover:bg-slate-800/60 disabled:opacity-50';

const WHAT_A_CHECK_SENDS =
  'A check asks GitHub for the list of releases. It sends no version, no identifier and nothing about you or your work, ' +
  'and it appears in Activity like anything else that leaves this computer. A download is checked against its SHA-256 ' +
  'before it can be run, and nothing is installed until you press Restart and install.';

export default function UpdatesSection({ Row }: UpdatesSectionProps) {
  const { status, message, busy, start, answer, check, download, install } = useUpdateStore();

  useEffect(() => {
    void start();
  }, [start]);

  if (!status) return <Row label="Updates" detail="Checking…" />;

  if (!status.known) {
    return (
      <Row
        label="Updates"
        value="not available"
        state="absent"
        detail="This is a development build with no release number, so it cannot tell whether anything is newer."
      />
    );
  }

  const latest = status.latest;
  const value = status.ready && latest
    ? `${latest.tag} ready`
    : status.phase === 'downloading'
      ? 'downloading'
      : latest
        ? `${latest.tag} available`
        : status.phase === 'up_to_date'
          ? 'up to date'
          : status.current ?? '';

  return (
    <>
      <Row
        label="Updates"
        value={value}
        state={latest ? 'warn' : 'neutral'}
        detail={`This is ${status.current}. ${WHAT_A_CHECK_SENDS}`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>
            <input
              type="checkbox"
              data-testid="update-checks-switch"
              checked={status.checks === true}
              disabled={busy}
              onChange={(event) => void answer(event.target.checked)}
            />
            Check for a newer version when Zaram opens
          </label>
          <button type="button" data-testid="update-check-now" className={BUTTON} disabled={busy} onClick={() => void check()}>
            Check now
          </button>
          {latest && !status.ready && status.phase !== 'downloading' && status.can_install && (
            <button type="button" data-testid="update-download" className={BUTTON} disabled={busy} onClick={() => void download()}>
              Download {sizeOf(latest.installer.size)}
            </button>
          )}
          {status.ready && status.can_install && (
            <button type="button" data-testid="update-install" className={BUTTON} disabled={busy} onClick={() => void install()}>
              Restart and install
            </button>
          )}
          {latest && !status.can_install && (
            <button type="button" data-testid="update-page" className={BUTTON} onClick={() => openInBrowser(latest.page)}>
              Open the release page
            </button>
          )}
        </div>
      </Row>
      {latest && !status.can_install && status.manual_reason && (
        <Row label="Updates" state="neutral" detail={status.manual_reason} />
      )}
      {message && <Row label="Updates" state="warn" detail={message} />}
    </>
  );
}
