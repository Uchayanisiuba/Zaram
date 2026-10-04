/**
 * What a new tab offers: the things Zaram has running.
 *
 * Asked for 3 October 2026 with a screenshot of Claude's new-tab page, and
 * narrowed the next day — *"make it such that it only shows the ones
 * launched or opened by Zaram."*
 *
 * The first version listed everything on the machine, grouped, with the
 * noise collapsed behind a disclosure. It was tidy and it was still a port
 * scan: 46 listeners on the maintainer's machine, 44 of them Discord,
 * OneDrive, Epic Games and svchost. What is here now is the list Zaram can
 * answer for — the dev servers it started, and its own backend.
 *
 * So there is no second group and no disclosure. Everything shown is
 * Zaram's, which is why every row can be pressed without a caveat.
 */
import { useEffect, useState } from 'react';
import { Globe, Server } from 'lucide-react';

import { fetchLocalServers, type LocalServer } from '@/services/localServersClient';

interface Props {
  /** Open this address in the current tab. */
  onOpen: (url: string) => void;
}

export default function NewTabPage({ onOpen }: Props) {
  const [servers, setServers] = useState<LocalServer[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let live = true;
    fetchLocalServers().then((listing) => {
      if (!live) return;
      setServers(listing.servers);
      setLoaded(true);
    });
    return () => {
      live = false;
    };
  }, []);

  return (
    <div className="h-full w-full overflow-auto px-6 py-10">
      <div className="mx-auto w-full max-w-lg">
        {loaded && servers.length === 0 && (
          <p
            className="py-10 text-center text-sm"
            style={{ color: 'var(--color-text-muted)' }}
            data-testid="nothing-running"
          >
            {/* Says what would put something here. "Nothing running" with
                no next step reads as a broken panel rather than an empty
                one. */}
            Zaram has not started anything yet. Ask it to run a project, or
            type an address above.
          </p>
        )}

        {servers.length > 0 && (
          <ul
            className="divide-y overflow-hidden rounded-xl"
            style={{
              borderColor: 'var(--color-border-subtle)',
              border: '1px solid var(--color-border-subtle)',
            }}
          >
            {servers.map((server) => (
              <li key={server.url} style={{ borderColor: 'var(--color-border-subtle)' }}>
                <button
                  type="button"
                  data-testid={`server-${server.port}`}
                  onClick={() => onOpen(server.url)}
                  className="group flex w-full items-center gap-3 px-4 py-3 text-left transition"
                  style={{ background: 'transparent' }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--color-glass)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <Server
                    size={15}
                    aria-hidden
                    style={{
                      color:
                        server.origin === 'zaram'
                          ? 'var(--color-text-muted)'
                          : 'var(--color-cyan-light)',
                    }}
                  />
                  <span className="min-w-0 flex-1">
                    <span
                      className="block truncate text-sm"
                      style={{ color: 'var(--color-text)' }}
                    >
                      {server.name}
                    </span>
                    {server.runner && (
                      <span
                        className="block truncate text-xs"
                        style={{ color: 'var(--color-text-faint)' }}
                      >
                        {server.runner}
                      </span>
                    )}
                  </span>
                  <span
                    className="shrink-0 text-xs"
                    style={{
                      color: 'var(--color-text-muted)',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    :{server.port}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        <p
          className="mt-8 flex items-start gap-2 text-xs leading-relaxed"
          style={{ color: 'var(--color-text-muted)' }}
        >
          <Globe size={13} className="mt-0.5 shrink-0" aria-hidden />
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
