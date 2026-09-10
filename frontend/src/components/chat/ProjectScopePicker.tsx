/**
 * Which project this conversation belongs to, and a way to make one.
 *
 * M8 built the scope field, the recall filter, the migration and the promotion
 * evidence, and shipped with nothing telling the engine which project was
 * active — so every fact landed `global` and `promotion_candidates()` could
 * only ever return an empty list. This is the control that closes that.
 *
 * **Deliberately small and beside the input, not a surface.** The navigation is
 * six nodes and a scope selector holds nothing — it is a property of the
 * conversation, so it lives in the conversation. It also sits where the
 * consequence is: the user can see which project a message will be filed under
 * at the moment they write it.
 *
 * Creation, and only creation — 10 September 2026
 * ----------------------------------------------
 * `CLAUDE.md` splits the two: *"Work is the output, Project is the
 * organisation of it… Project creates, names, types, assigns, moves and
 * deletes."* So this offers the first of those and none of the rest. Renaming,
 * re-scoping, assigning artifacts and deleting stay on the Project surface,
 * where deleting can properly ask what becomes of the facts and files a
 * project holds — a question a dropdown must never try to ask.
 *
 * **Rule 7h argues for it rather than against.** *Offer at the moment of
 * doubt; never make the user choose in advance.* Wanting a project you do not
 * have yet, mid-conversation, is that moment. Sending someone to another
 * surface to create it and come back is precisely the tax that rule refuses.
 *
 * **Type is asked here because it cannot be asked later.** `ProjectType`'s own
 * docstring: chosen at creation *"because that is the only moment the user
 * actually knows — and because rule 7e forbids asking a question the system
 * could answer from behaviour, which this one cannot be."* It activates a
 * pack. `general` is the default so the question is answerable by someone who
 * does not want to decide yet.
 *
 * **Root appears only for a coding project**, because that is the only type it
 * means anything for. `main.py` treats *"a coding project nobody has pointed
 * at a repository yet"* as one of three ways to mean no folder, and this is
 * the field that closes it. Nothing else is asked: no description, no colour,
 * no tags. Every extra field at creation asks the user to predict the future.
 *
 * The list comes from `/projects` now, not `/artifacts/projects`
 * -------------------------------------------------------------
 * The artifact-derived list only knew projects that had already produced a
 * file, so a project created and not yet used was invisible in the one control
 * that scopes it. With creation here that stops being a wrinkle and becomes a
 * contradiction — a project made in this dropdown would vanish from it. The
 * project store is the thing that knows what projects exist.
 */
import { useCallback, useEffect, useState } from 'react';
import { FolderOpen } from 'lucide-react';

import { useChatStore } from '@/stores/chatStore';

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** The sentinel `<option>` that opens the form. Not a project id, and shaped
 *  so it cannot collide with one. */
const NEW = '__new__';

/** Mirrors `ProjectType` in `backend/projects/records.py`. A type the backend
 *  does not know is a 400, so these are the backend's strings verbatim rather
 *  than a friendlier set mapped on the way out. */
const TYPES: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'general', label: 'General' },
  { value: 'business', label: 'Business' },
  { value: 'coding', label: 'Coding' },
  { value: '3d', label: '3D' },
  { value: 'mcp', label: 'MCP' },
];

type Entry = { id: string; label: string };

export default function ProjectScopePicker() {
  const projectId = useChatStore((s) => s.projectId);
  const setProject = useChatStore((s) => s.setProject);

  const [projects, setProjects] = useState<Entry[]>([]);
  const [failed, setFailed] = useState(false);

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [type, setType] = useState('general');
  const [root, setRoot] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/projects`);
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      const list: Entry[] = Array.isArray(data?.projects)
        ? data.projects
            .map((p: unknown) => {
              const row = p as { id?: unknown; name?: unknown };
              const id = String(row?.id ?? '');
              // The name if the store has one, the id otherwise. Never a
              // prettified id — that would be a value nobody entered.
              const label = typeof row?.name === 'string' && row.name ? row.name : id;
              return { id, label };
            })
            .filter((e: Entry) => e.id)
        : [];
      setProjects(list);
      setFailed(false);
    } catch {
      // A project list we could not fetch is not an empty project list.
      // Saying so beats silently offering "No project" as though it were
      // the only option — the user would file work under the wrong scope
      // and never know a choice existed.
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // The stored project may not be in the fetched list. Keeping it as an option
  // means a scope never silently resets to none.
  const options: Entry[] =
    projectId && !projects.some((p) => p.id === projectId)
      ? [{ id: projectId, label: projectId }, ...projects]
      : projects;

  async function create() {
    const trimmed = name.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: trimmed,
          type,
          // Sent only when it means something. An empty root on a general
          // project is a field the backend would have to decide to ignore.
          ...(type === 'coding' && root.trim() ? { root: root.trim() } : {}),
        }),
      });
      if (!res.ok) {
        // The backend's own words. `_checked_root` refuses a path that does
        // not exist and says which — replacing that with "could not create"
        // would throw away the only sentence that tells the user what to fix.
        let detail = `Could not create the project (${res.status})`;
        try {
          const body = await res.json();
          if (typeof body?.detail === 'string') detail = body.detail;
        } catch {
          /* a non-JSON error body is still an error */
        }
        setError(detail);
        return;
      }
      const made = await res.json();
      const id = String(made?.id ?? '');
      await load();
      if (id) setProject(id);
      setCreating(false);
      setName('');
      setRoot('');
      setType('general');
    } catch {
      setError('Could not reach the backend.');
    } finally {
      setBusy(false);
    }
  }

  if (creating) {
    return (
      <div className="flex flex-col gap-1 text-[11px] text-slate-500">
        <div className="flex items-center gap-1.5">
          <FolderOpen size={12} aria-hidden className="shrink-0" />
          <input
            autoFocus
            aria-label="New project name"
            placeholder="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void create();
              // Escape leaves without creating. A form that can only be left
              // by succeeding is a trap in a control this small.
              if (e.key === 'Escape') setCreating(false);
            }}
            className="bg-transparent text-[11px] text-slate-300 outline-none border-b border-slate-700 focus:border-slate-500 min-w-0 flex-1"
          />
          <select
            aria-label="Project type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="bg-transparent text-[11px] text-slate-400 outline-none cursor-pointer"
          >
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void create()}
            disabled={!name.trim() || busy}
            className="text-[11px] text-slate-300 disabled:text-slate-600 hover:text-slate-100"
          >
            {busy ? 'Creating…' : 'Create'}
          </button>
          <button
            type="button"
            onClick={() => setCreating(false)}
            className="text-[11px] text-slate-600 hover:text-slate-400"
          >
            Cancel
          </button>
        </div>
        {/* Only for coding, because it is the sandbox and means nothing
            elsewhere. Typed rather than browsed: the renderer cannot open a
            native folder dialog, and a button that opens nothing is worse
            than a field that works. */}
        {type === 'coding' && (
          <input
            aria-label="Repository folder"
            placeholder="Repository folder (optional)"
            value={root}
            onChange={(e) => setRoot(e.target.value)}
            className="bg-transparent text-[11px] text-slate-400 outline-none border-b border-slate-800 focus:border-slate-600 ml-[18px]"
          />
        )}
        {error && (
          <span className="text-amber-500/80 ml-[18px]" role="alert">
            {error}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
      <FolderOpen size={12} aria-hidden className="shrink-0" />
      <label htmlFor="project-scope" className="sr-only">
        Project this conversation belongs to
      </label>
      <select
        id="project-scope"
        value={projectId ?? ''}
        onChange={(e) => {
          const next = e.target.value;
          if (next === NEW) {
            setCreating(true);
            setError(null);
            return;
          }
          setProject(next || null);
        }}
        className="bg-transparent text-[11px] text-slate-400 outline-none cursor-pointer hover:text-slate-300 focus:text-slate-200 transition-colors"
      >
        {/* Not "All projects". No project active means facts are captured as
            global — about the user rather than about a piece of work — which
            is a different claim from "every project at once". */}
        <option value="">No project</option>
        {options.map((p) => (
          <option key={p.id} value={p.id}>
            {p.label}
          </option>
        ))}
        <option value={NEW}>New project…</option>
      </select>
      {failed && (
        <span className="text-slate-600" title="Could not reach the backend">
          · list unavailable
        </span>
      )}
    </div>
  );
}
