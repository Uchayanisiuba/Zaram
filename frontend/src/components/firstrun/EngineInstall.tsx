/**
 * Getting the local engine: the executor for "Set up a local model".
 *
 * Reported 14 October 2026 against alpha.6: *"the local model download option is
 * not clickable"*. On a machine with no engine, that is the first and the most
 * prominent offer on the screen, and `FirstRunPanel` rendered it greyed with
 * "Zaram can't set this up for you yet" — which, to somebody who just installed
 * a local-first assistant, reads as the product not working.
 *
 * **What this does, and what it does not.** It opens the engine's own download
 * page in the person's browser and then watches for the engine to start. It does
 * not download or run an installer itself. Fetching and silently running a
 * program of that size is a decision with its own consent, its own failure modes
 * (a half-written installer, an installer that needs a window) and no way to be
 * tried on a machine that already has one, and `CLAUDE.md` is plain that starting
 * what a person installed is a different act from acquiring something for them.
 * Opening a page is the person's own browser's request, not Zaram's, so nothing
 * here is egress.
 *
 * **It moves on by itself.** Once the page has been opened the panel asks
 * readiness again every few seconds, so the screen changes to "Download a model
 * to start with" the moment the engine answers — nobody has to come back and
 * press anything. A manual *check again* sits beside it for the case where the
 * engine starts and the screen has not noticed.
 *
 * The address is the one place it is written down. It is a page, not a file, so
 * a change at the other end costs a redirect rather than a broken button.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { openInBrowser } from '@/lib/openInBrowser';

/** Where the engine's installer for Windows is offered. */
export const ENGINE_DOWNLOAD_URL = 'https://ollama.com/download/windows';

/** How often the screen asks whether the engine has started, once the page is open. */
export const WATCH_EVERY_MS = 4000;

interface EngineInstallProps {
  /** Ask readiness again; the engine answering changes what the panel offers. */
  onCheck: () => void;
}

export default function EngineInstall({ onCheck }: EngineInstallProps) {
  const [opened, setOpened] = useState(false);
  // Held in a ref so the interval always calls the current handler without
  // restarting the clock every time the parent re-renders.
  const check = useRef(onCheck);
  useEffect(() => {
    check.current = onCheck;
  }, [onCheck]);

  useEffect(() => {
    if (!opened) return undefined;
    const timer = setInterval(() => check.current(), WATCH_EVERY_MS);
    return () => clearInterval(timer);
  }, [opened]);

  const open = useCallback(() => {
    openInBrowser(ENGINE_DOWNLOAD_URL);
    setOpened(true);
  }, []);

  return (
    <div data-testid="engine-install" className="flex flex-col gap-2 text-xs leading-relaxed">
      <p style={{ color: 'var(--color-text-muted)' }}>
        Zaram will open the download page for the engine that runs models on your own
        computer. Install it and leave it running — this screen moves on by itself once
        it can see it, and then offers the first model. Nothing you type leaves your
        computer.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          data-testid="open-engine-download"
          onClick={open}
          className="rounded-lg px-3 py-1.5 text-xs"
          style={{ border: '1px solid var(--color-cyan)', color: 'var(--color-cyan-light)' }}
        >
          {opened ? 'Open the download page again' : 'Open the download page'}
        </button>
        {opened && (
          <button
            type="button"
            data-testid="check-engine"
            onClick={onCheck}
            className="rounded-lg px-3 py-1.5 text-xs"
            style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }}
          >
            I’ve installed it — check again
          </button>
        )}
      </div>
      {opened && (
        <p role="status" style={{ color: 'var(--color-text-muted)' }}>
          Waiting for the engine to start…
        </p>
      )}
    </div>
  );
}
