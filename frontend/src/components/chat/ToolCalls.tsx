/**
 * What the model actually did to reach an answer, as it does it.
 *
 * **The backend has emitted this since the tool loop shipped and nothing
 * rendered it.** `StreamEvent.tool_call` carried the server, the tool and the
 * gate's verdict for every call; `chatClient.parseEvent` dropped it in its
 * default case. So a reply that searched a repository and read two files looked
 * exactly like one answered from memory — and the working, which is the whole
 * difference between a claim and a checkable claim, was invisible.
 *
 * `CLAUDE.md`: *"Show routing decisions in plain language"*, and *"disabled
 * capabilities are visible, not silent"*. A refused tool changed the answer;
 * saying so is not a debug affordance.
 *
 * **Not styled as the model speaking.** Same posture as `NoticeCard`: this is
 * Zaram reporting on itself, and putting it in the reply's own voice would
 * attribute Zaram's bookkeeping to the model.
 *
 * Live while it runs, folded once it is done
 * ------------------------------------------
 * Asked for on 7 September 2026 against Claude Code, which shows work in
 * progress as it happens and then folds it into one line — *"Ran 4 commands,
 * searched code ›"* — so a finished exchange reads as prose rather than as a
 * log. That is the right shape: while a coding task runs, the tool line is the
 * only thing on screen, because a generation that may call a tool is buffered
 * and the answer cannot stream.
 *
 * **One thing is deliberately not copied: a refusal never folds.** Collapsing
 * is for work that went as asked. A tool the gate stopped, or one waiting on a
 * confirmation, changed what the answer could be — hiding that behind a
 * chevron would make the product quieter exactly where it has to be loudest,
 * and "disabled capabilities are visible, not silent" is not a preference
 * about summaries. So the fold covers `allow` and nothing else.
 *
 * Still one line per call and nothing more. The *arguments* are not shown — a
 * `read_lines` on a 400-line range is a wall of numbers that tells a reader
 * nothing they wanted — and neither is the result, which is the file contents
 * and belongs in the model's context rather than on the screen.
 */
import { useState } from 'react';
import { Check, ChevronRight, CircleAlert, Clock } from 'lucide-react';
import type { ChatToolCall } from '../../stores/chatStore';

/** How each verdict reads. The gate's word, not the model's.
 *
 *  `allow` is deliberately the quietest of the three: a tool that ran as
 *  intended is the ordinary case, and drawing it in a warning colour would
 *  train the eye past the two that matter. */
const VERDICTS: Record<string, { Icon: typeof Check; color: string; label: string }> = {
  allow: { Icon: Check, color: 'var(--color-text-faint)', label: 'ran' },
  confirm: { Icon: Clock, color: 'var(--color-amber, #d97706)', label: 'waiting on you' },
  refuse: { Icon: CircleAlert, color: 'var(--color-amber, #d97706)', label: 'did not run' },
};

const UNKNOWN = { Icon: CircleAlert, color: 'var(--color-amber, #d97706)', label: '' };

/** What each tool reads as in a summary line.
 *
 *  Only the tools that exist. **There is no "wrote" or "patched" here and that
 *  is not an omission**: the code pack ships `list_files`, `read_lines` and
 *  `search_code`, and `CLAUDE.md` keeps every mutative tool out of scope until
 *  v1 ships. A verb for an action the product cannot take would be a label
 *  waiting for a feature, and the first person to read it would believe Zaram
 *  had edited their repository. Anything unrecognised falls back to its own
 *  name, which is honest and ages correctly when a tool is added. */
const PHRASES: Record<string, (n: number) => string> = {
  search_code: (n) => (n === 1 ? 'searched code' : `searched code ${n}×`),
  read_lines: (n) => (n === 1 ? 'read a file' : `read ${n} files`),
  list_files: (n) => (n === 1 ? 'listed files' : `listed files ${n}×`),
};

/** "Searched code, read 3 files" — distinct actions, in the order first used. */
export function summarise(calls: ChatToolCall[]): string {
  const counts = new Map<string, number>();
  for (const call of calls) counts.set(call.tool, (counts.get(call.tool) ?? 0) + 1);

  const entries = [...counts.entries()];
  const parts = entries.map(([tool, n]) => {
    const phrase = PHRASES[tool];
    return phrase ? phrase(n) : n === 1 ? tool : `${tool} ${n}×`;
  });
  if (!parts.length) return '';

  const joined = parts.join(', ');
  // Sentence case only when the line opens with a phrase we wrote. A tool name
  // is an identifier, and `some_new_tool` capitalised to `Some_new_tool` is no
  // longer the thing a reader would grep for — the fallback exists precisely so
  // an unknown tool arrives intact.
  const opensWithProse = PHRASES[entries[0][0]] !== undefined;
  return opensWithProse ? joined.charAt(0).toUpperCase() + joined.slice(1) : joined;
}

function CallLine({ call }: { call: ChatToolCall }) {
  const { Icon, color, label } = VERDICTS[call.verdict] ?? UNKNOWN;
  return (
    <li
      className="flex items-start gap-1.5 text-[10px] leading-snug"
      style={{ color: 'var(--color-text-muted)' }}
      data-verdict={call.verdict}
    >
      <Icon size={11} className="mt-px shrink-0" style={{ color }} aria-hidden />
      <span style={{ fontFamily: 'var(--font-mono)' }}>
        {call.server}/{call.tool}
      </span>
      {label && <span style={{ color: 'var(--color-text-faint)' }}>· {label}</span>}
      {/* The reason only when there is one, and there is one exactly when
          something did not go as asked. A "ran" carries none, and inventing
          filler for it would make the line longer and say less. */}
      {call.reason && call.verdict !== 'allow' && (
        <span style={{ color: 'var(--color-text-faint)' }}>· {call.reason}</span>
      )}
    </li>
  );
}

export default function ToolCalls({
  calls,
  active = false,
}: {
  calls: ChatToolCall[];
  /** The reply is still being written, so this is work in progress.
   *
   *  Live work stays open: folding it would hide the only thing on screen
   *  while a buffered generation decides what to do next. */
  active?: boolean;
}) {
  const [open, setOpen] = useState(false);
  if (!calls.length) return null;

  const ran = calls.filter((c) => c.verdict === 'allow');
  // Everything the gate did not simply allow, kept out of the fold entirely.
  const notable = calls.filter((c) => c.verdict !== 'allow');
  const expanded = open || active;

  return (
    <div className="mt-2" data-testid="tool-calls">
      {ran.length > 0 && (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={expanded}
          className="flex items-center gap-1 text-[10px] leading-snug"
          style={{ color: 'var(--color-text-muted)' }}
          data-testid="tool-summary"
        >
          <ChevronRight
            size={11}
            className="shrink-0 transition-transform"
            style={{ transform: expanded ? 'rotate(90deg)' : 'none' }}
            aria-hidden
          />
          <span>{summarise(ran)}</span>
          {active && (
            <span style={{ color: 'var(--color-text-faint)' }} aria-hidden>
              …
            </span>
          )}
        </button>
      )}

      {/* The fold, and only `allow` is inside it. */}
      {expanded && ran.length > 0 && (
        <ul className="mt-1 flex flex-col gap-1 pl-3">
          {ran.map((call, i) => (
            <CallLine key={`${call.server}/${call.tool}/${i}`} call={call} />
          ))}
        </ul>
      )}

      {/* Never folded. See the note at the top of the file. */}
      {notable.length > 0 && (
        <ul className="mt-1 flex flex-col gap-1">
          {notable.map((call, i) => (
            <CallLine key={`n/${call.server}/${call.tool}/${i}`} call={call} />
          ))}
        </ul>
      )}
    </div>
  );
}
