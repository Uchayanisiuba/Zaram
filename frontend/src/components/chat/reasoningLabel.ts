/**
 * One line for a collapsed thinking panel, in the model's own words.
 *
 * Asked for on 19 September 2026 with Claude as the reference: thinking shown
 * as one quiet line that changes as the work moves, the full text one click
 * away. The rule that decides what the line *is*:
 *
 * 1. The checklist's current `doing` item, when the model keeps one — that is
 *    the most honest statement of what it is doing right now, and it was
 *    written for exactly this purpose.
 * 2. Otherwise the first sentence of the **latest paragraph** of the
 *    reasoning so far. A thinking model paragraphs its work, and each
 *    paragraph opens by saying what it is about; the last one is where it is.
 *
 * **Never a paraphrase.** No second model call to summarise, and no template
 * that guesses — `CLAUDE.md`: never render invented values, and a summary of
 * the model's mind is a value like any other. Every character shown here was
 * written by the model or by the model's own plan.
 */

/** Longest the line may be, in characters, before it is cut at a word. */
export const MAX_LABEL = 80;

/** The opening sentence of the last non-empty paragraph, or ''. */
export function latestThought(text: string): string {
  const paragraphs = (text || '')
    .split(/\n\s*\n/)
    .map((p) => p.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
  const last = paragraphs[paragraphs.length - 1];
  if (!last) return '';
  // The first sentence: up to the first terminal mark followed by a space or
  // the end. A paragraph still being written has no terminal mark yet and is
  // taken whole, so the line moves as the model writes.
  const match = last.match(/^(.+?[.!?])(?:\s|$)/);
  return clip(match ? match[1] : last);
}

/** The line for the panel: the plan's `doing` item first, else the thought. */
export function reasoningLabel(text: string, doing?: string | null): string {
  const item = (doing || '').replace(/\s+/g, ' ').trim();
  if (item) return clip(item);
  return latestThought(text);
}

/** Cut at a word boundary with an ellipsis, never mid-word. */
export function clip(line: string): string {
  const s = line.trim();
  if (s.length <= MAX_LABEL) return s;
  const cut = s.slice(0, MAX_LABEL);
  const at = cut.lastIndexOf(' ');
  return `${(at > MAX_LABEL / 2 ? cut.slice(0, at) : cut).replace(/[\s,;:]+$/, '')}…`;
}
