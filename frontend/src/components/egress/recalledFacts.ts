/**
 * Finding the recalled facts inside an outbound request, and taking them out.
 *
 * The confirmation dialog's useful case is not "send everything" or "send
 * nothing" — it is *send this question, but not my day rate*. Rule 4 says the
 * user can remove any stored fact and see the effect, and a dialog that could
 * only refuse the whole request would be offering a coarser choice than the
 * product has already promised.
 *
 * So the facts have to be findable in the body. They are: the engine writes
 * them into the system prompt as `[M1] (2026-08-11) …` lines inside a block it
 * delimits, and that shape is what this reads. Two consequences worth stating.
 *
 * **This parses the body rather than being told.** The alternative was a second
 * field on `EgressRequest` listing the facts, which would have made the dialog
 * show one thing while the wire carried another the moment the two drifted. The
 * literal text is the record; a chip is a view of it.
 *
 * **Anything unrecognised yields no chips, never a guess.** A body that is not
 * JSON, or is JSON in a shape this does not know, gets the plain confirmation:
 * the literal text, and send or don't. Inventing chips over a body we cannot
 * parse would let a user believe they removed something that then left anyway,
 * which is the one failure worse than not offering the removal at all.
 */

/** The block the engine wraps recalled memories in. */
const BLOCK_HEADER = '=== WHAT YOU REMEMBER ABOUT THIS USER ===';
/** Its terminator: a run of `=`. Matched by shape, not by exact length. */
const BLOCK_FOOTER = /^={6,}$/;
/** `[M1] (2026-08-11) the fact itself` */
const FACT_LINE = /^\[M(\d+)\]\s*\((\d{4}-\d{2}-\d{2})\)\s*(.*)$/;

export interface RecalledFact {
  /** `M1`. Identifies the line for removal; never shown to the user. */
  marker: string;
  /** ISO date the fact was stored. */
  when: string;
  /** The fact, as the model would read it. */
  text: string;
}

interface ParsedBody {
  parsed: Record<string, unknown>;
  messages: Array<Record<string, unknown>>;
}

function readMessages(body: string | null): ParsedBody | null {
  if (!body) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(body);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== 'object') return null;
  const messages = (parsed as Record<string, unknown>).messages;
  if (!Array.isArray(messages)) return null;
  return {
    parsed: parsed as Record<string, unknown>,
    messages: messages as Array<Record<string, unknown>>,
  };
}

/** Every recalled fact the outbound request is carrying, in order. */
export function readRecalledFacts(body: string | null): RecalledFact[] {
  const doc = readMessages(body);
  if (!doc) return [];

  const facts: RecalledFact[] = [];
  for (const message of doc.messages) {
    const content = message.content;
    if (typeof content !== 'string') continue;
    for (const line of content.split('\n')) {
      const match = FACT_LINE.exec(line.trim());
      if (match) {
        facts.push({ marker: `M${match[1]}`, when: match[2], text: match[3].trim() });
      }
    }
  }
  return facts;
}

/**
 * The same request with the named facts struck out.
 *
 * Returns `null` when nothing changed — the caller sends no body at all in that
 * case, so an untouched request keeps its original bytes rather than being
 * re-serialised into an equivalent-but-different string.
 *
 * When the last fact goes, the surrounding block goes with it. An empty "what
 * you remember" header followed by instructions about memories that are not
 * there is not what the user asked for when they struck the only one.
 */
export function withoutRecalledFacts(
  body: string | null,
  markers: readonly string[],
): string | null {
  if (!body || markers.length === 0) return null;
  const doc = readMessages(body);
  if (!doc) return null;

  const removing = new Set(markers);
  let changed = false;

  const rewritten = doc.messages.map((message) => {
    const content = message.content;
    if (typeof content !== 'string') return message;

    const kept = content.split('\n').filter((line) => {
      const match = FACT_LINE.exec(line.trim());
      if (!match) return true;
      const drop = removing.has(`M${match[1]}`);
      if (drop) changed = true;
      return !drop;
    });

    const survivors = kept.some((line) => FACT_LINE.test(line.trim()));
    const next = survivors ? kept : stripEmptyBlock(kept);
    return { ...message, content: next.join('\n') };
  });

  if (!changed) return null;
  return JSON.stringify({ ...doc.parsed, messages: rewritten });
}

/** Drop the memory block entirely, header through terminator. */
function stripEmptyBlock(lines: string[]): string[] {
  const start = lines.findIndex((line) => line.trim() === BLOCK_HEADER);
  if (start === -1) return lines;

  let end = start + 1;
  while (end < lines.length && !BLOCK_FOOTER.test(lines[end].trim())) end += 1;
  if (end >= lines.length) return lines; // Unterminated: leave it alone.

  return [...lines.slice(0, start), ...lines.slice(end + 1)];
}
