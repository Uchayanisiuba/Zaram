/**
 * What Zaram can do for you, on a machine where it does not know you yet.
 *
 * `groundedPrompts` beside this file is the better offer and goes first: a
 * question about *your* folder, *your* project, *your* obligations, grounded
 * in a measurement. But it is empty on a fresh install by design — it will not
 * invent a client — and what a person saw there was one line telling them to
 * go and configure Knowledge. True, and not an answer to the question they
 * actually had, which is *what is this for*.
 *
 * Read from OpenWorker's `SessionIntro` on 15 September 2026, which is the
 * best-solved version of this screen: a greeting, **exactly three** concrete
 * tasks, and the composer. Three rules taken from it, and they are the whole
 * design here:
 *
 * 1. **The sub-line is the outcome, never the feature.** "A document in Work,
 *    written from your words" — not "document generation". Somebody deciding
 *    whether to type anything is deciding whether they want the result.
 * 2. **Connection state is a dot, in one vocabulary, everywhere.** Lit means
 *    this works right now, on this machine, measured. Unlit means it needs
 *    something first, and then the row's meaning *is* the setup — so the
 *    action becomes "Configure", pointing at the one surface that fixes it.
 * 3. **Never advertise what has not been run.** Every task here exercises a
 *    path that works today. A capability that has not been seen end to end
 *    does not get a row, however good it would look.
 *
 * Nothing here is a status claim on its own: `ready` is computed from things
 * the interface has actually read — whether a model can answer, whether any
 * folder has been indexed, whether a tool server is reachable. An unread
 * signal is `false`, never an optimistic default, for the same reason
 * `vram_bytes` returns `None` rather than `0`.
 */

/** The one thing a task needs before it can do anything. */
export type Requirement = 'model' | 'documents' | 'tools';

export interface StarterTask {
  /** Goes into the composer, ready to send or edit. */
  prompt: string;
  /** What you get. The outcome, in the person's terms. */
  outcome: string;
  needs: Requirement;
  /** Shown instead of Start when the requirement is not met. */
  configure: { label: string; node: 'knowledge' | 'settings' };
}

/** What the interface has measured. `false` means "read and not there"; the
 *  caller passes `false` for anything it could not read at all, which keeps a
 *  failed fetch from lighting a dot. */
export interface Capabilities {
  model: boolean;
  documents: boolean;
  tools: boolean;
}

export interface OfferedTask extends StarterTask {
  ready: boolean;
}

const TASKS: StarterTask[] = [
  {
    prompt: 'Turn these notes into a proposal I can send:\n\n',
    outcome: 'A document in Work, written from your words — not a chat reply.',
    needs: 'model',
    configure: { label: 'Add a model or a key', node: 'settings' },
  },
  {
    prompt: 'What have I committed to, and when is it due?',
    outcome: 'Dates and commitments out of your own files, each showing the clause it came from.',
    needs: 'documents',
    configure: { label: 'Point Zaram at a folder', node: 'knowledge' },
  },
  {
    prompt: 'Explain how this project works, starting from the entry point.',
    outcome: 'An answer that names the files it read, all of it on your machine.',
    needs: 'tools',
    configure: { label: 'Attach a tool', node: 'settings' },
  },
];

/**
 * The three tasks, each carrying whether it can run right now.
 *
 * Order is fixed rather than sorted by readiness. A list that reshuffles as
 * folders are indexed teaches nobody where anything is, and the unlit rows are
 * doing real work — they are the honest list of what this product is for,
 * which is exactly what a person on a fresh install is trying to find out.
 */
export function starterTasks(capabilities: Capabilities): OfferedTask[] {
  return TASKS.map((task) => ({ ...task, ready: capabilities[task.needs] }));
}

/**
 * How many starter tasks to show beneath `n` grounded prompts.
 *
 * Three rows in total, always. Grounded prompts are about the person's own
 * material and win every time; starters fill what is left. With three grounded
 * prompts there are no starters at all, which is the intended end state: a
 * screen that stops explaining itself once it has something better to say.
 */
export function fillTo(groundedCount: number, total = 3): number {
  return Math.max(0, total - groundedCount);
}
