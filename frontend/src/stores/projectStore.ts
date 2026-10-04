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
  /** The repository a coding project reads. **This is the sandbox boundary**,
   *  not a convenience: the code tools resolve every path against it and refuse
   *  anything landing outside.
   *
   *  Empty for every other type, and empty for a coding project nobody has
   *  pointed at a repository yet — which is a real state and the one worth
   *  rendering, because in it every tool call refuses. */
  root: string;
  /** Whether Zaram may change files under `root`. Off by default. Each edit
   *  is a git commit the user can revert, which is what makes a remembered
   *  grant acceptable — and it lives on the row so it is visible where it can
   *  be withdrawn. */
  writes: boolean;
  /** Whether Zaram may run the project's own detected commands — tests,
   *  builds, linters — never a shell. Off by default, separate from `writes`
   *  because it is a different thing to consent to. */
  runs: boolean;
  /** Whether Zaram may drive the app in a browser — open the page, click,
   *  type. Off by default and separate from `runs` for the same reason
   *  `runs` is separate from `writes`: running the project's named
   *  commands is bounded, and pressing whatever happens to be on a page
   *  is not. A dev build pointed at a production database is where the
   *  difference bites. */
  drives: boolean;
  /** Whether Zaram may run terminal commands in this project.
   *
   *  A capability rather than a hole, and separate from `runs` for the
   *  reason `runners.py` exists: a named build command is bounded and a
   *  shell is not. Off by default, and the maintainer's decision was that
   *  granting it is per project rather than per call. */
  shell: boolean;
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
  create: (
    name: string,
    type: ProjectType,
    note?: string,
    root?: string,
  ) => Promise<Project | null>;
  rename: (id: string, name: string) => Promise<void>;
  setType: (id: string, type: ProjectType) => Promise<void>;
  /** Point a coding project at its repository, or pass "" to withdraw it.
   *
   *  Withdrawing is a real operation rather than a no-op: it is how somebody
   *  takes the folder away without deleting the project and everything scoped
   *  to it. The backend refuses a path that is not a folder and says so, which
   *  is why this surfaces `error` like the rest of the store. */
  setRoot: (id: string, root: string) => Promise<void>;
  /** Allow or withdraw file edits in a coding project's folder. The code
   *  pack's confirm-once, per project rather than per server. */
  setWrites: (id: string, writes: boolean) => Promise<void>;
  /** Allow or withdraw running the project's detected commands. */
  setRuns: (id: string, runs: boolean) => Promise<void>;
  /** Allow or withdraw driving the app in a browser. */
  setDrives: (id: string, drives: boolean) => Promise<void>;
  /** Whether Zaram may run terminal commands in this project.
   *
   *  **The backend has had `set_shell` and a `shell` column since the
   *  terminal landed, and nothing here could turn it on.** The other
   *  three grants had setters; this one did not, so the one grant the
   *  maintainer had explicitly decided should be per project — *"once
   *  the user grants it permission the permission is per project"* —
   *  was reachable only by editing the database. Found 4 October 2026
   *  while building the permission card that needed it. */
  setShell: (id: string, shell: boolean) => Promise<void>;
  /** The names of the commands `setRuns` would allow, detected from the
   *  repository — so the control can say what it grants. Empty on any failure;
   *  this is a label, never a gate. */
  fetchRunners: (id: string) => Promise<string[]>;
  /** Reverse one commit Zaram made in the project's repository. Resolves to
   *  `null` on success or the backend's own sentence on refusal — "that commit
   *  is not one Zaram made", "your local changes would be overwritten". */
  revertCommit: (id: string, commit: string) => Promise<string | null>;
  /** Stop the app Zaram started in a project. True when something stopped. */
  stopApp: (id: string) => Promise<boolean>;
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

/**
 * A request that reports instead of throwing.
 *
 * Returns the `Response` when the backend answered and liked it, or the
 * sentence to show when it did not — a refusal, or a request that never
 * completed at all.
 *
 * **Why this exists.** `load` had a try/catch and eight siblings did not, so
 * a dropped connection rejected out of the store and into whichever component
 * was awaiting. Reported 3 October 2026 as a Create button that did nothing:
 * `CreateRow` set `busy` before awaiting, the rejection skipped
 * `setBusy(false)`, and the button disabled itself permanently with no
 * message, because `set({ error })` was never reached.
 *
 * Returning the sentence rather than throwing is the part that lasts. A
 * convention that every action needs a `try` is a convention the ninth action
 * forgets; there is no `try` to forget when there is no throw.
 */
async function send(
  url: string,
  init: RequestInit,
  fallback: string,
): Promise<Response | string> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (e) {
    // Naming the cause matters here. "That project could not be created"
    // alone sends somebody back to check what they typed, when the true
    // answer is that Zaram's backend did not answer at all — which is a
    // different problem with a different fix.
    const why = e instanceof Error ? e.message : String(e);
    return `${fallback} Zaram's backend did not answer (${why}).`;
  }
  if (!res.ok) return await readError(res, fallback);
  return res;
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

  create: async (name, type, note = '', root = '') => {
    set({ error: null });
    const res = await send(
      `${API}/projects`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, type, note, root }),
      },
      'That project could not be created.',
    );
    if (typeof res === 'string') {
      set({ error: res });
      return null;
    }
    let project: Project;
    try {
      project = (await res.json()) as Project;
    } catch {
      // Answered 2xx and sent something unreadable. `load()` is the honest
      // recovery: if the project is really there it appears in the list, and
      // the message is still shown because this call cannot say that it is.
      await get().load();
      set({ error: 'That project could not be created.' });
      return null;
    }
    // Reload rather than pushing the response: the list carries counts this
    // response does not, and a row that renders without them would flicker.
    await get().load();
    return project;
  },

  rename: async (id, name) => {
    const res = await send(
      `${API}/projects/${encodeURIComponent(id)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      },
      'That project could not be renamed.',
    );
    if (typeof res === 'string') {
      set({ error: res });
      return;
    }
    await get().load();
  },

  setRoot: async (id, root) => {
    set({ error: null });
    // The backend's own sentence — "C:\nope is not a folder on this machine"
    // is something a person can act on, and a 400 is not.
    const res = await send(
      `${API}/projects/${encodeURIComponent(id)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ root }),
      },
      'That folder could not be set.',
    );
    if (typeof res === 'string') {
      set({ error: res });
      return;
    }
    await get().load();
  },

  setWrites: async (id, writes) => {
    set({ error: null });
    const res = await send(
      `${API}/projects/${encodeURIComponent(id)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ writes }),
      },
      'That could not be changed.',
    );
    if (typeof res === 'string') {
      set({ error: res });
      return;
    }
    await get().load();
  },

  setRuns: async (id, runs) => {
    set({ error: null });
    const res = await send(
      `${API}/projects/${encodeURIComponent(id)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ runs }),
      },
      'That could not be changed.',
    );
    if (typeof res === 'string') {
      set({ error: res });
      return;
    }
    await get().load();
  },

  setDrives: async (id, drives) => {
    set({ error: null });
    const res = await send(
      `${API}/projects/${encodeURIComponent(id)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ drives }),
      },
      'That could not be changed.',
    );
    if (typeof res === 'string') {
      set({ error: res });
      return;
    }
    await get().load();
  },

  setShell: async (id, shell) => {
    set({ error: null });
    const res = await send(
      `${API}/projects/${encodeURIComponent(id)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shell }),
      },
      'That could not be changed.',
    );
    if (typeof res === 'string') {
      set({ error: res });
      return;
    }
    await get().load();
  },

  fetchRunners: async (id) => {
    try {
      const res = await fetch(`${API}/projects/${encodeURIComponent(id)}/runners`);
      if (!res.ok) return [];
      const body = (await res.json()) as { runners?: { name: string }[] };
      return (body.runners ?? []).map((r) => r.name);
    } catch {
      return [];
    }
  },

  revertCommit: async (id, commit) => {
    try {
      const res = await fetch(`${API}/projects/${encodeURIComponent(id)}/revert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ commit }),
      });
      if (!res.ok) return await readError(res, 'That change could not be reverted.');
      return null;
    } catch {
      return 'That change could not be reverted.';
    }
  },

  stopApp: async (id) => {
    try {
      const res = await fetch(`${API}/projects/${encodeURIComponent(id)}/app/stop`, { method: 'POST' });
      if (!res.ok) return false;
      const body = (await res.json()) as { stopped?: boolean };
      return body.stopped === true;
    } catch {
      return false;
    }
  },

  setType: async (id, type) => {
    const res = await send(
      `${API}/projects/${encodeURIComponent(id)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type }),
      },
      'That project type could not be changed.',
    );
    if (typeof res === 'string') {
      set({ error: res });
      return;
    }
    await get().load();
  },

  adopt: async (id, name, type) => {
    // The id is passed through untouched and is never re-derived from the
    // name. Every file and every fact in this group points at this exact
    // string; slugifying the name here would create a *different* project and
    // adopt nothing, which is the one failure this whole path exists to end.
    const res = await send(
      `${API}/projects/${encodeURIComponent(id)}/adopt`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, type }),
      },
      `${id} could not be adopted.`,
    );
    if (typeof res === 'string') {
      set({ error: res });
      return;
    }
    await get().load();
  },

  remove: async (id, contents) => {
    // `contents` is required by the signature rather than defaulted, so a
    // caller cannot delete facts by forgetting an argument.
    const res = await send(
      `${API}/projects/${encodeURIComponent(id)}?contents=${contents}`,
      { method: 'DELETE' },
      'That project could not be deleted.',
    );
    if (typeof res === 'string') {
      set({ error: res });
      return;
    }
    await get().load();
  },
}));
