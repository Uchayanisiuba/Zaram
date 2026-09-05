import { create } from 'zustand';

/**
 * Projects, as objects.
 *
 * The composer's scope picker used to read `/artifacts/projects`, which derives
 * its list from saved files — so a project you had only *talked* about did not
 * exist, one made by a typo could never be removed, and there was nowhere to
 * keep the type that activates a pack. This reads `/projects`, which is the
 * list of projects that exist.
 *
 * Both endpoints remain and answer different questions: `/artifacts/projects`
 * is "which projects hold files", used by Work to offer a filter that cannot
 * lead to an empty list.
 */

const API = import.meta.env.VITE_ZARAM_API ?? '';

/** The types that activate a pack. `general` exists so the question is
 *  answerable by someone who has not decided yet — a required choice at
 *  creation is a wall in front of the first project anyone makes. */
export const PROJECT_TYPES = ['general', 'business', 'coding', '3d', 'mcp'] as const;
export type ProjectType = (typeof PROJECT_TYPES)[number];

export interface Project {
  id: string;
  name: string;
  type: ProjectType;
  created_at: number;
  note: string;
  /** `project:<id>` — the scope its facts carry. */
  scope: string;
  /** How many generated files are assigned to it. */
  artifacts: number;
  /** How many facts are scoped to it, or **-1 when the Spine could not say**.
   *
   *  Not folded into 0. "0 facts" on a delete confirmation that then destroys
   *  eleven of them is the exact failure this count exists to prevent, so the
   *  unknown case has to stay distinguishable all the way to the button. */
  facts: number;
}

/** What happens to a project's facts when it is deleted. Never defaulted
 *  silently — a container quietly exercising rule 4 on the user's behalf is how
 *  someone loses a client's rates by tidying a sidebar. */
export type DeleteContents = 'keep' | 'delete';

/** A group that exists on its contents but is not a project.
 *
 *  Files and facts carry whatever `project_id` the request had, and neither
 *  creation path used to check that the project existed — so a stale selection
 *  or a typo produced a group Work groups files under and Project could not
 *  show, rename or delete. Assignment now validates its destination, which
 *  turned that into a one-way door: a file can leave and cannot return.
 *
 *  This is the way back in. It is not a second kind of project — it is the
 *  absence of one, listed so it can be fixed. */
export interface UnclaimedGroup {
  id: string;
  artifacts: number;
  /** Facts under `project:<id>`, or **-1 when the Spine could not say**. Same
   *  rule as `Project.facts`: the unknown case stays distinguishable, because
   *  "no facts" and "could not count" lead to different decisions. */
  facts: number;
}

interface ProjectStore {
  projects: Project[];
  /** Ordered by id, and normally empty. A non-empty list is a defect the user
   *  is being offered a fix for, not a feature of the screen. */
  unclaimed: UnclaimedGroup[];
  loading: boolean;
  error: string | null;

  load: () => Promise<void>;
  create: (name: string, type: ProjectType, note?: string) => Promise<Project | null>;
  rename: (id: string, name: string) => Promise<void>;
  setType: (id: string, type: ProjectType) => Promise<void>;
  adopt: (id: string, name: string, type: ProjectType) => Promise<void>;
  remove: (id: string, contents: DeleteContents) => Promise<void>;
}

async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return typeof body?.detail === 'string' ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  unclaimed: [],
  loading: false,
  error: null,

  load: async () => {
    set({ loading: true, error: null });
    try {
      const res = await fetch(`${API}/projects`);
      if (!res.ok) {
        set({ loading: false, error: await readError(res, `Could not load projects (${res.status}).`) });
        return;
      }
      const body: { projects?: Project[] } = await res.json();
      set({ projects: body.projects ?? [], loading: false });
    } catch (e) {
      set({
        loading: false,
        error: e instanceof Error ? e.message : 'Could not load projects.',
      });
      return;
    }

    // Separate request, and deliberately not fatal. The unclaimed list is a
    // repair offer; a backend too old to serve it, or a failure reading it,
    // must not take the projects screen down with it — the user still has
    // projects to look at, and an error banner over a working list would be
    // Zaram reporting its own new endpoint as their problem.
    try {
      const res = await fetch(`${API}/projects/unclaimed`);
      if (!res.ok) {
        set({ unclaimed: [] });
        return;
      }
      const body: { unclaimed?: UnclaimedGroup[] } = await res.json();
      set({ unclaimed: body.unclaimed ?? [] });
    } catch {
      set({ unclaimed: [] });
    }
  },

  create: async (name, type, note = '') => {
    set({ error: null });
    const res = await fetch(`${API}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, type, note }),
    });
    if (!res.ok) {
      set({ error: await readError(res, 'That project could not be created.') });
      return null;
    }
    const project: Project = await res.json();
    // Reload rather than pushing the response: the list carries counts this
    // response does not, and a row that renders without them would flicker.
    await get().load();
    return project;
  },

  rename: async (id, name) => {
    const res = await fetch(`${API}/projects/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) {
      set({ error: await readError(res, 'That project could not be renamed.') });
      return;
    }
    await get().load();
  },

  setType: async (id, type) => {
    const res = await fetch(`${API}/projects/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type }),
    });
    if (!res.ok) {
      set({ error: await readError(res, 'That project type could not be changed.') });
      return;
    }
    await get().load();
  },

  adopt: async (id, name, type) => {
    // The id is passed through untouched and is never re-derived from the
    // name. Every file and every fact in this group points at this exact
    // string; slugifying the name here would create a *different* project and
    // adopt nothing, which is the one failure this whole path exists to end.
    const res = await fetch(`${API}/projects/${encodeURIComponent(id)}/adopt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, type }),
    });
    if (!res.ok) {
      set({ error: await readError(res, `${id} could not be adopted.`) });
      return;
    }
    await get().load();
  },

  remove: async (id, contents) => {
    // `contents` is required by the signature rather than defaulted, so a
    // caller cannot delete facts by forgetting an argument.
    const res = await fetch(
      `${API}/projects/${encodeURIComponent(id)}?contents=${contents}`,
      { method: 'DELETE' },
    );
    if (!res.ok) {
      set({ error: await readError(res, 'That project could not be deleted.') });
      return;
    }
    await get().load();
  },
}));
