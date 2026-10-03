/**
 * What a new tab offers: the servers running on this machine.
 *
 * Asked for 3 October 2026 with a screenshot of Claude's new-tab page —
 * *"I want them to see all the running servers ... Zaram's front end, back
 * end etc. I want them to see Ride Share's own, or any other project of
 * theirs."*
 *
 * **Detected, not declared.** The backend reads the process table rather
 * than a project's `package.json` scripts, so every row is a port that is
 * actually accepting connections rather than one that could be.
 *
 * The third group is collapsed rather than dropped. Measured on the
 * maintainer's machine: 46 things were listening and 44 were Discord,
 * OneDrive, Epic Games and svchost. Listing those is a port scan; hiding
 * them outright would be deciding that nobody wants to open Ollama's port,
 * which is not true.
 */
import { useEffect, useState } from 'react';
import { ChevronDown, Globe, Server } from 'lucide-react';

import { fetchLocalServers, type LocalServer } from '@/services/localServersClient';

interface Props {
  /** Open this address in the current tab. */
  onOpen: (url: string) => void;
}

export default function NewTabPage({ onOpen }: Props) {
  const [servers, setServers] = useState<LocalServer[]>([]);
  const [hidden, setHidden] = useState(0);
  const [showAll, setShowAll] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let live = true;
    fetchLocalServers().then((listing) => {
      if (!live) return;
      setServers(listing.servers);
      setHidden(listing.hidden);
      setLoaded(true);
    });
    return () => {
      live = false;
    };
  }, []);

  const mine = servers.filter((s) => s.origin !== 'other');
  const rest = servers.filter((s) => s.origin === 'other');
  const shown = showAll ? [...mine, ...rest] : mine;

  return (
    <div className="h-full w-full overflow-auto bg-slate-950 px-6 py-10 text-slate-200">
      <div className="mx-auto w-full max-w-xl">
        {loaded && shown.length === 0 && (
          <p className="py-10 text-center text-sm text-slate-500">
            {/* Honest about which of the two it is. "Nothing is running" and
                "this machine will not say" are different facts, and sharing
                a sentence makes the second look like the first. */}
            Nothing is listening on this machine, or the process table could
            not be read. Type an address above.
          </p>
        )}

        {shown.length > 0 && (
          <ul className="divide-y divide-slate-800 overflow-hidden rounded-lg border border-slate-800">
            {shown.map((server) => (
              <li key={server.port}>
                <button
                  type="button"
                  data-testid={`server-${server.port}`}
                  onClick={() => onOpen(server.url)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-slate-900"
                >
                  <Server
                    size={16}
                    className={server.origin === 'other' ? 'text-slate-600' : 'text-indigo-400'}
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1 truncate text-sm">{server.name}</span>
                  <span className="shrink-0 font-mono text-xs text-slate-500">:{server.port}</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {!showAll && hidden > 0 && (
          <button
            type="button"
            data-testid="show-other-servers"
            onClick={() => setShowAll(true)}
            className="mt-3 flex items-center gap-1.5 text-xs text-slate-500 transition hover:text-slate-300"
          >
            <ChevronDown size={14} aria-hidden />
            {/* Says what it is hiding rather than how many rows there are:
                somebody reading this needs to know it is their own machine's
                other processes, not more of their projects. */}
            {hidden} other {hidden === 1 ? 'process' : 'processes'} on this machine
          </button>
        )}

        <p className="mt-8 flex items-start gap-2 text-xs leading-relaxed text-slate-500">
          <Globe size={14} className="mt-0.5 shrink-0" aria-hidden />
          <span>
            Pages on this machine open straight away — nothing leaves the
            device, so there is nothing to consent to. Anywhere else is
            logged, and needs browsing turned on in Settings.
          </span>
        </p>
      </div>
    </div>
  );
}
