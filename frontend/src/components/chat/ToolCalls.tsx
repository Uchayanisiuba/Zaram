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
 * Still one line per call. The *arguments* are not shown — a `read_lines` on
 * a 400-line range is a wall of numbers that tells a reader nothing they
 * wanted. **The result is, on request — revised 12 September 2026.** This
 * used to say the result "belongs in the model's context rather than on the
 * screen", and that is right as a default and wrong as a rule: a step that
 * cannot be opened cannot be checked, and "read `readiness.py:156-181`" is a
 * claim until the lines are there. So each row that ran opens to a bounded
 * pane of what came back — see `StepOutput` — and stays a row until asked.
 */
import { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { Check, ChevronRight, CircleAlert, Clock, Wrench } from 'lucide-react';
import type { ChatToolCall } from '../../stores/chatStore';
import { grantTool } from '@/services/toolsClient';
import ActivityPanel from './ActivityPanel';
import AppCard from './AppCard';
import ChangeCard from './ChangeCard';
import StepOutput from './StepOutput';

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
 *  Only the tools that exist. Until 12 September that meant the three reads,
 *  and the note here said a verb for writing would be a label waiting for a
 *  feature. The feature landed — `write_file`, `edit_file` and `run_command`
 *  in the code pack — so the verbs exist now, and a change additionally gets
 *  its own unfolded card (`ChangeCard`) because a summary line is not where a
 *  reader can judge a diff. Anything unrecognised still falls back to its own
 *  name, which is honest and ages correctly when a tool is added. */
const PHRASES: Record<string, (n: number) => string> = {
  search_code: (n) => (n === 1 ? 'searched code' : `searched code ${n}×`),
  read_lines: (n) => (n === 1 ? 'read a file' : `read ${n} files`),
  list_files: (n) => (n === 1 ? 'listed files' : `listed files ${n}×`),
  write_file: (n) => (n === 1 ? 'wrote a file' : `wrote ${n} files`),
  edit_file: (n) => (n === 1 ? 'edited a file' : `edited ${n} files`),
  run_command: (n) => (n === 1 ? 'ran a command' : `ran ${n} commands`),
  find_symbol: (n) => (n === 1 ? 'looked up a symbol' : `looked up ${n} symbols`),
  read_library_docs: (n) => (n === 1 ? 'read library docs' : `read library docs ${n}×`),
  plan: (n) => (n === 1 ? 'planned' : `planned ${n}×`),
  start_app: () => 'started the app',
  stop_app: () => 'stopped the app',
  look_at_app: (n) => (n === 1 ? 'looked at the app' : `looked at the app ${n}×`),
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

/**
 * The answer to *"this needs your say-so"*, on the row that says it.
 *
 * **Built 15 September 2026, and what it replaced was a dead end.** A tool the
 * gate held returned "needs your say-so", the loop stopped, and there was
 * nowhere to say so: the only way through was Settings → Tools, finding the
 * server, and granting the tool by name — at the exact moment somebody is
 * trying to get something done. Rule 7j says *confirm once per destination,
 * then remember*; the "then remember" half had an endpoint and no button.
 *
 * It allows the **tool**, not the call, and says so. That is the gate's own
 * unit of consent and it is what the reason text already promises — "Zaram
 * will stop asking about this tool once you allow it". Allowing a single call
 * would need the paused call kept somewhere, which is a store this does not
 * have and a promise it will not imply.
 *
 * **A deletion never gets this button.** `grantable` comes from the gate,
 * which keeps asking about destructive tools however much has been granted —
 * so offering it here would promise something the gate will not honour, and a
 * button that changes nothing is worse than no button.
 */
function AllowTool({ call, onAllowed }: { call: ChatToolCall; onAllowed: () => void }) {
  const [state, setState] = useState<'idle' | 'working' | 'failed'>('idle');
  if (!call.grantable || call.verdict !== 'confirm') return null;
  return (
    <span className="flex items-center gap-2 pl-[18px] pt-0.5">
      <button
        type="button"
        disabled={state === 'working'}
        onClick={async () => {
          setState('working');
          try {
            await grantTool(call.server, call.tool);
            onAllowed();
          } catch {
            // Said on the row rather than thrown away: a grant that failed
            // silently would look like a grant that worked and did nothing.
            setState('failed');
          }
        }}
        className="text-xs"
        style={{ color: 'var(--color-cyan-light)', background: 'none', border: 0, padding: 0, cursor: 'pointer' }}
        data-testid="allow-tool"
      >
        {state === 'working' ? 'Allowing…' : `Allow ${call.tool}`}
      </button>
      <span className="text-[11px]" style={{ color: 'var(--color-text-faint)' }}>
        {state === 'failed'
          ? 'That did not save — try again, or allow it in Settings → Tools.'
          : 'and stop asking about it'}
      </span>
    </span>
  );
}

function CallLine({ call, onAllowed }: { call: ChatToolCall; onAllowed?: () => void }) {
  const { Icon, color, label } = VERDICTS[call.verdict] ?? UNKNOWN;
  const [showOutput, setShowOutput] = useState(false);
  const openable = Boolean(call.output);
  return (
    <li
      className="flex flex-col text-xs leading-snug"
      style={{ color: 'var(--color-text-muted)' }}
      data-verdict={call.verdict}
    >
      {/* A row is a button only when there is something behind it. A chevron
          on a step with no output would open onto nothing, which teaches the
          reader that chevrons are furniture. */}
      <button
        type="button"
        onClick={openable ? () => setShowOutput((v) => !v) : undefined}
        aria-expanded={openable ? showOutput : undefined}
        disabled={!openable}
        className="flex items-start gap-1.5 text-left disabled:cursor-default"
        style={{ color: 'inherit', background: 'none', border: 0, padding: 0 }}
        data-testid="step-row"
      >
        {openable ? (
          <ChevronRight
            size={11}
            className="mt-px shrink-0 transition-transform"
            style={{ transform: showOutput ? 'rotate(90deg)' : 'none', color }}
            aria-hidden
          />
        ) : (
          <Icon size={11} className="mt-px shrink-0" style={{ color }} aria-hidden />
        )}
        <span style={{ fontFamily: 'var(--font-mono)' }}>
          {call.server}/{call.tool}
        </span>
        {call.target && (
          <span className="break-all" style={{ color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}>
            {call.target}
          </span>
        )}
        {label && <span style={{ color: 'var(--color-text-faint)' }}>· {label}</span>}
        {/* The reason only when there is one, and there is one exactly when
            something did not go as asked. A "ran" carries none, and inventing
            filler for it would make the line longer and say less. */}
        {call.reason && call.verdict !== 'allow' && (
          <span style={{ color: 'var(--color-text-faint)' }}>· {call.reason}</span>
        )}
      </button>
      {onAllowed && <AllowTool call={call} onAllowed={onAllowed} />}
      {showOutput && <StepOutput text={call.output ?? ''} />}
    </li>
  );
}

export default function ToolCalls({
  calls,
  active = false,
  onAllowed,
}: {
  calls: ChatToolCall[];
  /** Called after a held tool has been allowed, so the shell can ask the
   *  question again — the tool is permitted now and the answer changes.
   *  Absent on a replayed history, where allowing settles nothing to retry. */
  onAllowed?: () => void;
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
  // And every change to a file, likewise never folded — see `ChangeCard`.
  const changes = calls.filter((c) => c.verdict === 'allow' && Boolean(c.diff));
  // A started app and what Zaram saw of it — see `AppCard`.
  const apps = calls.filter((c) => c.verdict === 'allow' && (Boolean(c.image) || Boolean(c.appUrl)));
  const expanded = open || active;

  return (
    <div className="mt-2" data-testid="tool-calls">
      {/* **The tools notification.** The card that used to sit under a reply
          said "14 attached tools are available" — offered, not used — and a
          person reading it asked whether all fourteen ran (13 September).
          What they asked for instead is this: a card about the tools that
          *were* used, in words, with an arrow that opens to each call. Same
          shape as `NoticeCard` so it reads as the one place tool activity
          lives; the words come from `summarise`, because "read two files,
          ran the tests" says more than a count. */}
      {ran.length > 0 && (
        <button
          type="button"
          onClick={() => (active ? setOpen((v) => !v) : setOpen(true))}
          aria-expanded={expanded}
          className="w-full rounded-lg px-3 py-2 flex items-center gap-2.5 text-left text-xs leading-snug surface"
          style={{ color: 'var(--color-text-muted)' }}
          data-testid="tool-summary"
        >
          <Wrench size={12} className="shrink-0" style={{ color: 'var(--color-text-muted)' }} aria-hidden />
          <span className="flex-1 min-w-0 truncate">
            <span style={{ color: 'var(--color-text)' }}>{active ? 'Using tools' : 'Used tools'}</span>
            {' — '}
            {summarise(ran)}
            {active && (
              <span style={{ color: 'var(--color-text-faint)' }} aria-hidden>
                {' …'}
              </span>
            )}
          </span>
          <ChevronRight
            size={12}
            className="shrink-0 transition-transform"
            style={{ transform: expanded ? 'rotate(90deg)' : 'none' }}
            aria-hidden
          />
        </button>
      )}

      {/* Live work unfolds in place: while a buffered generation decides what
          to do next this is the only thing on screen, and sending someone to a
          panel to watch it would take the conversation away from them. */}
      {active && ran.length > 0 && (
        <ul className="mt-1 flex flex-col gap-1 pl-3">
          {ran.map((call, i) => (
            <CallLine key={`${call.server}/${call.tool}/${i}`} call={call} />
          ))}
        </ul>
      )}

      {/* Finished work opens where the detail has room for what it was aimed
          at. The same overlay `ArtifactPreview` and `CitationPanel` use — one
          way to bring something forward is a thing users learn once. */}
      <AnimatePresence>
        {open && !active && (
          <ActivityPanel calls={calls} onClose={() => setOpen(false)} />
        )}
      </AnimatePresence>

      {changes.map((call, i) => (
        <ChangeCard key={`c/${call.commit || i}`} call={call} />
      ))}
      {apps.map((call, i) => (
        <AppCard key={`a/${call.image || call.appUrl || i}`} call={call} />
      ))}

      {/* Never folded. See the note at the top of the file. */}
      {notable.length > 0 && (
        <ul className="mt-1 flex flex-col gap-1">
          {notable.map((call, i) => (
            <CallLine
              key={`n/${call.server}/${call.tool}/${i}`}
              call={call}
              onAllowed={onAllowed}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
