/**
 * GitHub — connect an account, so Zaram can push a project, open a pull request
 * or file an issue when asked.
 *
 * The same arrangement the Claude and ChatGPT connectors use: a GitHub App the
 * person installs on the repositories they choose. The difference this section
 * has to say plainly is where the sign-in lives -- **on this computer**, sealed to
 * the Windows user, and never on a server of ours.
 *
 * Signing in is GitHub's device flow: Zaram shows a short code, the person types
 * it at github.com in their own browser, and the window polls until GitHub says
 * yes. No password and no token ever passes through this component.
 *
 * What it does not do, and says it does not: every action that changes something
 * on GitHub asks each time, there is no standing yes for it, and forgetting the
 * sign-in here does not revoke it on GitHub.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  disconnectGithub,
  fetchGithubRepositories,
  fetchGithubStatus,
  pollGithubConnect,
  startGithubConnect,
  type GithubDeviceCode,
  type GithubRepository,
  type GithubStatus,
} from '../../services/githubClient';
import { openInBrowser } from '../../lib/openInBrowser';

export interface GitHubSectionProps {
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

const ASKS_EVERY_TIME =
  'Every action that changes something on GitHub — a push, a pull request, an issue — asks you each time, ' +
  'and no standing yes can be kept for it. Zaram can reach only the repositories you choose on GitHub.';

export default function GitHubSection({ Row }: GitHubSectionProps) {
  const [status, setStatus] = useState<GithubStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [code, setCode] = useState<GithubDeviceCode | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [repositories, setRepositories] = useState<GithubRepository[] | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // A poll that comes back after Cancel, or after leaving, must not revive the flow.
  const live = useRef<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setStatus(await fetchGithubStatus());
      setLoadError(null);
    } catch (caught) {
      setStatus(null);
      setLoadError((caught as Error).message);
    }
  }, []);

  useEffect(() => {
    void reload();
    return () => {
      live.current = null;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [reload]);

  const stop = useCallback(() => {
    live.current = null;
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    setCode(null);
  }, []);

  const poll = useCallback(
    (flow: string, seconds: number) => {
      timer.current = setTimeout(async () => {
        if (live.current !== flow) return;
        try {
          const answer = await pollGithubConnect(flow);
          if (live.current !== flow) return;
          if (answer.state === 'pending') {
            poll(flow, answer.interval ?? seconds);
            return;
          }
          if (answer.state === 'done') {
            stop();
            setStatus(answer);
            setMessage(null);
            return;
          }
          stop();
          setMessage(
            answer.state === 'denied'
              ? 'GitHub said no — the sign-in was refused. Nothing was connected.'
              : answer.detail || 'The sign-in did not finish. Press Connect to try again.',
          );
        } catch (caught) {
          if (live.current !== flow) return;
          stop();
          setMessage((caught as Error).message);
        }
      }, seconds * 1000);
    },
    [stop],
  );

  const connect = useCallback(async () => {
    setBusy(true);
    setMessage(null);
    try {
      const started = await startGithubConnect();
      live.current = started.flow;
      setCode(started);
      poll(started.flow, started.interval);
    } catch (caught) {
      setMessage((caught as Error).message);
    } finally {
      setBusy(false);
    }
  }, [poll]);

  const disconnect = useCallback(async () => {
    setBusy(true);
    try {
      const answer = await disconnectGithub();
      setStatus(answer);
      setRepositories(null);
      setMessage(answer.note);
    } catch (caught) {
      setMessage((caught as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  const showRepositories = useCallback(async () => {
    setBusy(true);
    try {
      setRepositories((await fetchGithubRepositories()).repositories);
      setMessage(null);
    } catch (caught) {
      setMessage((caught as Error).message);
    } finally {
      setBusy(false);
    }
  }, []);

  if (loadError) {
    return <Row label="GitHub" value="unavailable" state="warn" detail={loadError} />;
  }
  if (!status) {
    return <Row label="GitHub" detail="Checking…" />;
  }
  if (!status.configured) {
    return (
      <Row
        label="GitHub"
        value="not set up"
        state="absent"
        detail="This build has no GitHub app registered, so there is nothing to connect to."
      />
    );
  }

  if (code) {
    return (
      <Row
        label="Connecting to GitHub"
        value={code.user_code}
        state="neutral"
        detail={
          'Type this code at GitHub to approve Zaram. Your password is never entered here and never reaches Zaram. ' +
          'This page finishes by itself once you approve.'
        }
      >
        <div className="flex flex-wrap gap-2">
          <button type="button" className={BUTTON} onClick={() => openInBrowser(code.verification_uri)}>
            Open GitHub
          </button>
          <button type="button" className={BUTTON} onClick={stop}>
            Cancel
          </button>
        </div>
      </Row>
    );
  }

  if (!status.connected) {
    return (
      <>
        <Row
          label="GitHub"
          value={status.expired ? 'sign-in ended' : 'not connected'}
          state={status.expired ? 'warn' : 'absent'}
          detail={
            (status.expired ? 'The sign-in ran out. Connect again to carry on. ' : '') +
            'Connect GitHub and Zaram can push the project you are working on, open pull requests and file issues when you ask. ' +
            'The sign-in stays on this computer, sealed to your Windows account. ' +
            ASKS_EVERY_TIME
          }
        >
          <button type="button" className={BUTTON} disabled={busy} onClick={() => void connect()}>
            Connect GitHub
          </button>
        </Row>
        {message && <Row label="GitHub" state="warn" detail={message} />}
      </>
    );
  }

  return (
    <>
      <Row
        label="GitHub"
        value={`connected as ${status.login}`}
        state="good"
        detail={
          (status.sealed === false
            ? 'The sign-in is stored on this computer but is not encrypted on this system. '
            : 'The sign-in is stored on this computer, sealed to your Windows account. ') + ASKS_EVERY_TIME
        }
      >
        <div className="flex flex-wrap gap-2">
          <button type="button" className={BUTTON} disabled={busy} onClick={() => openInBrowser(status.install_url)}>
            Choose repositories
          </button>
          <button type="button" className={BUTTON} disabled={busy} onClick={() => void showRepositories()}>
            Show what Zaram can reach
          </button>
          <button type="button" className={BUTTON} disabled={busy} onClick={() => void disconnect()}>
            Disconnect
          </button>
        </div>
      </Row>
      {repositories && (
        <Row
          label="Repositories Zaram can reach"
          value={String(repositories.length)}
          state={repositories.length ? 'good' : 'warn'}
          detail={
            repositories.length === 0
              ? 'None yet. Press Choose repositories and pick the ones Zaram may use.'
              : repositories
                  .map((r) => `${r.full_name}${r.private ? ' (private)' : ''}${r.can_push ? '' : ' — read only'}`)
                  .join('\n')
          }
        />
      )}
      {message && <Row label="GitHub" state="neutral" detail={message} />}
    </>
  );
}
