/**
 * The reply with its rows *between* the paragraphs, in the order it happened.
 *
 * `docs/PLAN.md` B2, 19 September 2026. A message used to be `text` plus a
 * separate `toolCalls[]` rendered under it, so "I'll read the store first" →
 * row → "The reducer is in …" → row → answer came out as all the prose, then
 * all the rows. Claude Code's transcript keeps the order, and the maintainer
 * named it as the reference.
 *
 * The record is not restructured. Each row keeps the length of the reply's
 * text at the moment it arrived (`ChatToolCall.at`), and this component cuts
 * the text at those offsets: chunk, the rows that arrived there, chunk, …
 * Rows with no offset — a history restored from before today, or a row that
 * arrived before any text — sit in front, which is where they happened.
 * Each group of rows is the existing `ToolCalls`, so folding, the change
 * cards, the held-tool button and the Activity panel are untouched; a group
 * folds to its own line where it sits.
 */
import type { ReactNode } from 'react';
import type { ChatToolCall } from '../../stores/chatStore';
import ToolCalls from './ToolCalls';

export interface Segment {
  kind: 'text' | 'rows';
  text?: string;
  calls?: ChatToolCall[];
}

/** Cut `text` at the offsets the rows arrived at. Pure, so it is testable
 *  without a DOM; empty chunks are dropped rather than rendered as gaps. */
export function segments(text: string, calls: ChatToolCall[]): Segment[] {
  const groups = new Map<number, ChatToolCall[]>();
  for (const call of calls) {
    const raw = typeof call.at === 'number' && Number.isFinite(call.at) ? call.at : 0;
    // Clamped: a row that arrived past the end of the text as it now stands
    // (the text was trimmed, or a marker was stripped) belongs at the end,
    // never off it.
    const at = Math.max(0, Math.min(raw, text.length));
    groups.set(at, [...(groups.get(at) ?? []), call]);
  }
  const offsets = [...groups.keys()].sort((a, b) => a - b);

  const out: Segment[] = [];
  let cursor = 0;
  for (const at of offsets) {
    if (at > cursor) out.push({ kind: 'text', text: text.slice(cursor, at) });
    out.push({ kind: 'rows', calls: groups.get(at) });
    cursor = Math.max(cursor, at);
  }
  if (cursor < text.length) out.push({ kind: 'text', text: text.slice(cursor) });
  return out;
}

export default function Interleaved({
  text,
  calls,
  active = false,
  onAllowed,
  renderText,
}: {
  text: string;
  calls: ChatToolCall[];
  active?: boolean;
  onAllowed?: () => void;
  /** How a chunk of the reply is drawn: the body, or the typewriter for the
   *  last chunk while streaming. `last` says which chunk this is. */
  renderText: (chunk: string, last: boolean) => ReactNode;
}) {
  const parts = segments(text, calls);
  const lastText = parts.map((p) => p.kind).lastIndexOf('text');
  return (
    <div className="flex flex-col gap-2" data-testid="interleaved">
      {parts.map((part, i) =>
        part.kind === 'text' ? (
          <div key={`t${i}`}>{renderText(part.text ?? '', i === lastText)}</div>
        ) : (
          <ToolCalls
            key={`r${i}`}
            calls={part.calls ?? []}
            // Only the last group is still live: an earlier one has prose
            // after it, which means the model moved on.
            active={active && i === parts.length - 1}
            onAllowed={onAllowed}
          />
        ),
      )}
    </div>
  );
}
