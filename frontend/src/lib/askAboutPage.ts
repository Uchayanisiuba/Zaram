/**
 * Asking Zaram about a page it wrote, from inside the preview.
 *
 * Asked for 5 October 2026: *"users should be able to select and highlight
 * elements of the page, right click and an Ask button shows up for users to
 * ask Zaram to make changes"*, and a **Fix this** for a page that stopped.
 * The same afternoon a change request came back as only the changed lines,
 * which nobody can run — so every request here asks for the whole page back.
 *
 * Each one is sent as a *revision* of the reply that wrote the page, so the
 * page travels with it whole (`core/revise.py` sends a code-bearing reply
 * uncut) and the model is answering about exactly that page, not about its
 * memory of it.
 *
 * What the frame reports is **page-controlled text** — the page can put
 * anything in its own markup — so it is bounded here and only ever rendered
 * as text. It never widens what anything may do; it is a description.
 */

/** One element the person pointed at, as the frame reported it. */
export interface PickedElement {
  tag: string;
  selector: string;
  text: string;
  html: string;
  rect: { x: number; y: number; w: number; h: number };
}

const clip = (value: unknown, max: number): string => {
  const text = typeof value === 'string' ? value : '';
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
};

const num = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) ? value : 0);

/** What the frame said, checked and bounded, or null if it is not a pick. */
export function readPick(detail: unknown): PickedElement | null {
  let raw: Record<string, unknown>;
  try {
    raw = typeof detail === 'string' ? JSON.parse(detail) : (detail as Record<string, unknown>);
  } catch {
    return null;
  }
  if (!raw || typeof raw !== 'object' || typeof raw.tag !== 'string' || !raw.tag) return null;
  const rect = (raw.rect ?? {}) as Record<string, unknown>;
  return {
    tag: clip(raw.tag, 24).toLowerCase(),
    selector: clip(raw.selector, 200),
    text: clip(raw.text, 160),
    html: clip(raw.html, 800),
    rect: { x: num(rect.x), y: num(rect.y), w: num(rect.w), h: num(rect.h) },
  };
}

/** How the element reads on the popover: `button#start` and its words. */
export function describe(picked: PickedElement): string {
  return picked.selector.split(' > ').pop() || picked.tag;
}

const WHOLE_PAGE = 'Keep everything else as it is, and reply with the whole updated page in one ```html block.';

function part(picked: PickedElement): string {
  return [
    `The part: <${picked.tag}> at \`${picked.selector}\``,
    picked.text ? `Its text: "${picked.text}"` : '',
    `Its markup:\n\`\`\`html\n${picked.html}\n\`\`\``,
  ]
    .filter(Boolean)
    .join('\n');
}

/** "Change this part of the page" — the person's words, about one element. */
export function changeRequest(picked: PickedElement, instruction: string): string {
  return `Change one part of the page.\n\n${part(picked)}\n\nWhat to change: ${instruction.trim()}\n\n${WHOLE_PAGE}`;
}

/** "What does this part do?" — an answer, not a rewrite. */
export function explainRequest(picked: PickedElement): string {
  return `What does this part of the page do, and how does it work?\n\n${part(picked)}\n\nAnswer in a few sentences; do not rewrite the page.`;
}

/** What Zaram says to the model when it ran a page before showing it and the
 *  page did not work. Written so the person reading the conversation can see
 *  why a message they did not type is there, and so a model with no memory of
 *  the check knows what was run and what is wanted back. */
export function checkFailedRequest(problems: readonly string[], several: boolean): string {
  const list = problems.slice(0, 4).map((p) => `- ${clip(p, 400)}`).join('\n');
  return (
    'Zaram ran this page before showing it, and it did not work:\n\n' +
    `${list}\n\n` +
    'Find the cause and fix it, checking every loop and every name the page uses. ' +
    (several
      ? 'Reply with every file again in full, each on a fence line with its name.'
      : 'Reply with the whole page in one ```html block.')
  );
}

/** The preview's fault report, handed back to be fixed. */
export function fixRequest(error: string, hosts: readonly string[] = []): string {
  const lines = [`The page stopped with this error: ${clip(error, 400)}`];
  if (hosts.length) {
    lines.push(
      `It also asked ${hosts.join(', ')} for part of itself, which the preview cannot load — ` +
        'use only three.js and its listed addons, or write it without a library.',
    );
  }
  lines.push('Find the cause and fix it, then reply with the whole page in one ```html block.');
  return lines.join('\n\n');
}
