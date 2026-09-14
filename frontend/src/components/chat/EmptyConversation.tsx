/**
 * The empty conversation: up to three things worth asking, each grounded.
 *
 * See `groundedPrompts` for the rule. Read once when the empty state mounts —
 * three small requests, each allowed to fail on its own; a failed one simply
 * contributes no prompt. With nothing to ground a prompt in, the state says
 * that plainly and points at Knowledge, rather than showing an example about
 * somebody who does not exist.
 */
import { useEffect, useState } from 'react';

import { fetchObligations, countObligations, type ObligationCounts } from '@/services/obligationsClient';
import { fetchSources, type IngestSource } from '@/services/ingestClient';
import type { Project } from '@/stores/projectStore';
import { useSystemStore } from '@/stores/systemStore';
import { groundedPrompts, type GroundedPrompt } from './groundedPrompts';

const API = import.meta.env.VITE_ZARAM_API ?? '';

async function fetchProjects(): Promise<Project[]> {
  const res = await fetch(`${API}/projects`);
  if (!res.ok) throw new Error(`Could not load projects (${res.status}).`);
  const body: { projects?: Project[] } = await res.json();
  return body.projects ?? [];
}

const settled = async <T,>(p: Promise<T>): Promise<T | null> => {
  try {
    return await p;
  } catch {
    return null;
  }
};

export default function EmptyConversation({ onPick }: { onPick: (prompt: string) => void }) {
  // `undefined` until read: the fallback must not flash before the prompts.
  // `null` when nothing could be read at all — an engine that is down is not
  // a Knowledge that is empty, and saying "nothing is indexed" off a failed
  // fetch would be a measured zero invented from an absent measurement.
  const [prompts, setPrompts] = useState<GroundedPrompt[] | null | undefined>(undefined);

  // Read again when the engine comes back: a list read while it was down is
  // `null`, and the prompts should appear the moment they can be measured.
  const backendOnline = useSystemStore((s) => s.backendOnline);
  useEffect(() => {
    let live = true;
    void (async () => {
      const [listing, sources, projects] = await Promise.all([
        settled(fetchObligations()),
        settled(fetchSources()),
        settled(fetchProjects()),
      ]);
      if (!live) return;
      if (listing === null && sources === null && projects === null) {
        setPrompts(null);
        return;
      }
      const obligations: ObligationCounts | null = listing ? countObligations(listing) : null;
      setPrompts(groundedPrompts({ obligations, sources: sources as IngestSource[] | null, projects }));
    })();
    return () => {
      live = false;
    };
  }, [backendOnline]);

  return (
    <div className="flex flex-col gap-3" data-testid="empty-conversation">
      <p className="t-kicker">Ask Zaram something</p>
      {prompts == null ? null : prompts.length === 0 ? (
        <p className="text-xs" style={{ margin: 0, color: 'var(--color-text-faint)' }}>
          Nothing is indexed yet. Point Knowledge at a folder and the suggestions here will be about it.
        </p>
      ) : (
        /* Suggestive, not a card: a quiet line per prompt, in the faint tone,
           brightening under the pointer. The maintainer saw the boxed version
           and called it too visible (14 September) — a suggestion is something
           to take or leave, and a box asks to be dealt with. */
        <ul className="flex flex-col gap-1.5" aria-label="Things worth asking">
          {prompts.map((p) => (
            <li key={p.prompt}>
              <button
                type="button"
                onClick={() => onPick(p.prompt)}
                className="group text-left text-sm leading-snug transition-colors"
                style={{ color: 'var(--color-text-faint)', background: 'none', border: 0, padding: 0, cursor: 'pointer' }}
                data-testid="grounded-prompt"
              >
                <span className="group-hover:text-[var(--color-text-muted-light)] transition-colors">
                  <span aria-hidden style={{ opacity: 0.6 }}>›  </span>
                  {p.prompt}
                </span>
                <span className="t-mono ml-2" style={{ color: 'var(--color-text-faint)', opacity: 0.8 }}>
                  {p.reason}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
