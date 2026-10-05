/**
 * Zaram asking for permission, where the asking happens.
 *
 * Asked for 4 October 2026: *"the UI when Zaram needs the user to grant
 * permissions, like using the terminal, should show up like a card with an
 * allow or deny button, or allow for this session or entire project."*
 *
 * **What this replaces was not nothing.** `AllowTool` already offered *for
 * this conversation* and *always*, and the reasoning behind it still holds
 * and is kept below. It was a row of text links under a tool row, which is
 * the right weight for a footnote and the wrong weight for a question —
 * the one moment in the product where Zaram has stopped and is waiting on
 * a person is the moment that should not look like a footnote.
 *
 * The rungs, and why there are four
 * ---------------------------------
 * Rule 7j: *confirm once per destination and data class, then remember*,
 * because *forty dialogs a day is a product nobody opens on day two*. Each
 * rung is a different span of "yes", and the span is the whole decision:
 *
 * * **Deny** — leave it refused. New, and the argument for it is that not
 *   pressing anything is indistinguishable from not noticing. It sends
 *   nothing: the call was already refused by the gate and the reply has
 *   already gone on without it, so this clears the question rather than
 *   answering it. The label says so.
 * * **This conversation** — what most people mean by yes: a yes for the
 *   task in hand. Without it the only choices are one call or forever,
 *   which is what pushes people to forever.
 * * **This project** — the maintainer's own decision about the terminal,
 *   *"once the user grants it permission the permission is per project"*.
 *   Offered only when the gate names a switch that would cover it, so the
 *   button cannot turn on a grant that settles nothing.
 * * **Always** — the rung Settings has always had, said here so nobody has
 *   to go and find it mid-task.
 * * **Run this once** — added 5 October 2026. A yes for *this call*, which
 *   is the one answer that settles a floor: an install, a delete, a hook.
 *   Those are not grantable, so before this the card offered only Deny and
 *   the call could not be approved from the conversation at all. It runs the
 *   call that was parked with the task — the one on this card — and never
 *   grants anything. Not offered for a send, nor for a call whose target the
 *   card cannot show; the backend decides both.
 *
 * Every rung that says yes carries the task on from where it stopped,
 * rather than asking the question again from nothing.
 *
 * **A destructive tool gets no buttons at all.** `grantable` comes from the
 * gate, which keeps asking about deletions however much has been granted —
 * offering a grant would promise something the gate will not honour, and a
 * button that changes nothing is worse than no button. The card still
 * appears, because the question was still asked; it just has nothing to
 * offer but Deny.
 */
import { useState } from 'react';
import { ShieldQuestion } from 'lucide-react';

import { allowToolForSession, grantTool } from '@/services/toolsClient';
import { useChatStore } from '@/stores/chatStore';
import type { AllowedResume, ChatToolCall } from '@/stores/chatStore';
import { useProjectStore } from '@/stores/projectStore';

/** What each project switch is called where a person can see it. */
const SWITCH_LABEL: Record<string, string> = {
  shell: 'run terminal commands',
  runs: 'run this project’s commands',
  drives: 'open and drive this project’s app',
  writes: 'change files in this project',
};

interface Props {
  call: ChatToolCall;
  /** The person said yes. With a parked task, `resume` says which task to
   *  carry on and whether the yes was for this one call. */
  onAllowed: (resume?: AllowedResume) => void;
}

export default function PermissionCard({ call, onAllowed }: Props) {
  const [state, setState] = useState<'idle' | 'working' | 'failed' | 'denied'>('idle');
  const sessionId = useChatStore((s) => s.sessionId);
  const projectId = useChatStore((s) => s.projectId);
  const setWrites = useProjectStore((s) => s.setWrites);
  const setRuns = useProjectStore((s) => s.setRuns);
  const setDrives = useProjectStore((s) => s.setDrives);
  const setShell = useProjectStore((s) => s.setShell);

  if (call.verdict !== 'confirm') return null;
  if (state === 'denied') return null;

  const scope = call.grantScope ?? '';
  // Only when there is a project to grant *on*. A switch with nowhere to
  // live is the control that settles nothing.
  const canGrantProject = Boolean(call.grantable && scope && projectId && SWITCH_LABEL[scope]);

  async function press(how: 'session' | 'project' | 'always') {
    setState('working');
    try {
      if (how === 'session') {
        await allowToolForSession(call.server, call.tool, sessionId);
      } else if (how === 'project' && projectId) {
        // Through the store rather than a bare PATCH, so the switch in
        // Project reflects it immediately — a grant given here and not
        // shown there is a consent with nowhere to withdraw it.
        const flip = { writes: setWrites, runs: setRuns, drives: setDrives, shell: setShell }[
          scope
        ];
        if (!flip) throw new Error(`no switch called ${scope}`);
        await flip(projectId, true);
      } else {
        await grantTool(call.server, call.tool);
      }
      onAllowed(call.heldTask ? { planId: call.heldTask, runHeld: false } : undefined);
    } catch {
      // Said on the card rather than thrown away: a grant that failed
      // silently would look like a grant that worked and did nothing.
      setState('failed');
    }
  }

  const busy = state === 'working';
  const canRunOnce = Boolean(call.once && call.heldTask);

  function runOnce() {
    // Nothing is granted: the backend runs the parked call with this one
    // yes, and the next call asks for itself.
    setState('working');
    onAllowed({ planId: call.heldTask as string, runHeld: true });
  }

  return (
    <div
      data-testid="permission-card"
      className="mt-2 rounded-xl px-4 py-3"
      style={{
        background: 'var(--color-glass)',
        // Amber, matching the `confirm` verdict's own colour. The card is
        // the same state the row reports, drawn larger.
        border: '1px solid rgba(217,119,6,0.35)',
      }}
    >
      <div className="flex items-start gap-2.5">
        <ShieldQuestion
          size={15}
          className="mt-0.5 shrink-0"
          style={{ color: 'var(--color-amber, #d97706)' }}
          aria-hidden
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>
            {/* The gate's own sentence, never one composed here. It already
                names what the tool does and what would permit it, and a
                second phrasing would be a second opinion about what was
                refused. */}
            {call.reason || `Zaram needs your say-so to use ${call.tool}.`}
          </p>
          {call.target && (
            <p
              className="mt-1 truncate text-xs"
              style={{ color: 'var(--color-text-faint)', fontFamily: 'var(--font-mono)' }}
              title={call.target}
            >
              {/* What it was aimed at. Model-written text, rendered as text:
                  *that* a tool ran is not checkable and *what it ran on*
                  is. */}
              {call.target}
            </p>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              data-testid="deny-tool"
              disabled={busy}
              onClick={() => setState('denied')}
              className="rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
              style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }}
            >
              Deny
            </button>

            {canRunOnce && (
              <button
                type="button"
                data-testid="run-once"
                disabled={busy}
                onClick={runOnce}
                className="rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
                style={{ border: '1px solid var(--color-cyan)', color: 'var(--color-cyan-light)' }}
              >
                Run this once
              </button>
            )}

            {call.grantable && (
              <>
                <button
                  type="button"
                  data-testid="allow-tool-session"
                  disabled={busy}
                  onClick={() => void press('session')}
                  className="rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
                  style={{
                    border: '1px solid var(--color-cyan)',
                    color: 'var(--color-cyan-light)',
                  }}
                >
                  Allow for this conversation
                </button>

                {canGrantProject && (
                  <button
                    type="button"
                    data-testid="allow-tool-project"
                    disabled={busy}
                    onClick={() => void press('project')}
                    className="rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
                    style={{
                      border: '1px solid var(--color-border)',
                      color: 'var(--color-text)',
                    }}
                  >
                    Allow for this project
                  </button>
                )}

                <button
                  type="button"
                  data-testid="allow-tool"
                  disabled={busy}
                  onClick={() => void press('always')}
                  className="rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
                  style={{ border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }}
                >
                  Always
                </button>
              </>
            )}
          </div>

          <p className="mt-2 text-[11px]" style={{ color: 'var(--color-text-faint)' }}>
            {/* Each press says what it costs, because the span is the
                decision. "Always" without "stops asking everywhere" is the
                offer without the deal. */}
            {busy
              ? 'Saving…'
              : state === 'failed'
                ? 'That did not save — try again, or allow it in Settings → Tools.'
                : !call.grantable
                  ? 'Zaram asks about this one every time, however much is allowed — it cannot be undone.'
                  : canGrantProject
                    ? `“This project” turns on ${SWITCH_LABEL[scope]}, and you can withdraw it in Project. “Always” stops Zaram asking anywhere.`
                    : '“Always” stops Zaram asking about this tool anywhere. You can withdraw it in Settings → Tools.'}
          </p>
        </div>
      </div>
    </div>
  );
}
