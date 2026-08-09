/**
 * Which project this conversation belongs to. Rule 7i's missing caller.
 *
 * M8 built the scope field, the recall filter, the migration and the promotion
 * evidence, and shipped with nothing telling the engine which project was
 * active — so every fact landed `global` and `promotion_candidates()` could
 * only ever return an empty list. This is the control that closes that.
 *
 * **Deliberately small and beside the input, not a surface.** The navigation is
 * five nodes and a scope selector holds nothing — it is a property of the
 * conversation, so it lives in the conversation. It also sits where the
 * consequence is: the user can see which project a message will be filed under
 * at the moment they write it.
 *
 * Options come from projects that already exist in Work. There is no
 * project-name store, so these are **ids, not names** — the same honesty Work
 * settled on. Turning `harbour` into "Harbour Lane Studio" would be a value
 * nobody entered.
 */
import { useEffect, useState } from 'react';
import { FolderOpen } from 'lucide-react';

import { useChatStore } from '@/stores/chatStore';

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export default function ProjectScopePicker() {
  const projectId = useChatStore((s) => s.projectId);
  const setProject = useChatStore((s) => s.setProject);

  const [projects, setProjects] = useState<string[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/artifacts/projects`);
        if (!res.ok) throw new Error(String(res.status));
        const data = await res.json();
        // `/artifacts/projects` returns `[{ id, count }]`, not `[string]`.
        // Assuming the simpler shape rendered an object as a React child and
        // took the whole conversation surface down with it — the same drift
        // that made `sampleArtifacts.ts` disagree with the backend model, and
        // the reason the client uses the backend's field names directly rather
        // than through a mapping layer.
        const ids = Array.isArray(data?.projects)
          ? data.projects
              .map((p: unknown) =>
                typeof p === 'string' ? p : String((p as { id?: unknown })?.id ?? ''),
              )
              .filter(Boolean)
          : [];
        if (!cancelled) setProjects(ids);
      } catch {
        // A project list we could not fetch is not an empty project list.
        // Saying so beats silently offering "No project" as though it were
        // the only option — the user would file work under the wrong scope
        // and never know a choice existed.
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // The stored project may not be in the fetched list — it was selected before,
  // and an artifact-derived list only knows projects that have produced files.
  // Keeping it as an option means a scope never silently resets to none.
  const options = projectId && !projects.includes(projectId)
    ? [projectId, ...projects]
    : projects;

  return (
    <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
      <FolderOpen size={12} aria-hidden className="shrink-0" />
      <label htmlFor="project-scope" className="sr-only">
        Project this conversation belongs to
      </label>
      <select
        id="project-scope"
        value={projectId ?? ''}
        onChange={(e) => setProject(e.target.value || null)}
        className="bg-transparent text-[11px] text-slate-400 outline-none cursor-pointer hover:text-slate-300 focus:text-slate-200 transition-colors"
      >
        {/* Not "All projects". No project active means facts are captured as
            global — about the user rather than about a piece of work — which
            is a different claim from "every project at once". */}
        <option value="">No project</option>
        {options.map((id) => (
          <option key={id} value={id}>
            {id}
          </option>
        ))}
      </select>
      {failed && (
        <span className="text-slate-600" title="Could not reach the backend">
          · list unavailable
        </span>
      )}
    </div>
  );
}
