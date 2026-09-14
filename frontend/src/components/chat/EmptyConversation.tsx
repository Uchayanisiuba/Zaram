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
  const [prompts, setPrompts] = useState<GroundedPrompt[] | undefined>(undefined);

  useEffect(() => {
    let live = true;
    void (async () => {
      const [listing, sources, projects] = await Promise.all([
        settled(fetchObligations()),
        settled(fetchSources()),
        settled(fetchProjects()),
      ]);
      if (!live) return;
      const obligations: ObligationCounts | null = listing ? countObligations(listing) : null;
      setPrompts(groundedPrompts({ obligations, sources: sources as IngestSource[] | null, projects }));
    })();
    return () => {
      live = false;
    };
  }, []);

  return (
    <div className="flex flex-col gap-3" data-testid="empty-conversation">
      <p className="t-kicker">Ask Zaram something</p>
      {prompts === undefined ? null : prompts.length === 0 ? (
        <p className="t-body" style={{ color: 'var(--color-text-muted)' }}>
          Nothing is indexed yet, so there is nothing to suggest. Point Knowledge at a
          folder and the prompts here will be about what is in it.
        </p>
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Things worth asking">
          {prompts.map((p) => (
            <li key={p.prompt}>
              <button
                type="button"
                onClick={() => onPick(p.prompt)}
                className="w-full text-left rounded-xl px-4 py-3 surface transition-colors hover:bg-white/[0.03]"
                data-testid="grounded-prompt"
              >
                <span className="t-body block">{p.prompt}</span>
                <span className="t-mono block mt-1">{p.reason}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
