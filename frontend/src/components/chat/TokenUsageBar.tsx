/**
 * What the last exchange cost, in tokens, in the green-plus / red-minus shape
 * every agentic tool now uses.
 *
 * Asked for on 7 September 2026 against a screenshot of Claude Code, whose
 * header carries `+8,507 −154` beside the branch. **That number is a diff stat
 * — lines added and removed — and Zaram cannot produce one**: the code pack's
 * tools are `list_files`, `read_lines` and `search_code`, all read-only, and
 * `CLAUDE.md` keeps every mutative tool out of scope until v1 ships. Nothing
 * edits a file, so there is nothing to add up. Borrowing the shape while
 * inventing the quantity is exactly the "status indicator over hardcoded data"
 * the UI principles forbid.
 *
 * So it counts the thing that is real and was invisible. `+` is tokens put in
 * front of the model this turn — the prompt as sent, which is mostly recall,
 * plus the reply. `−` is tokens a compaction took back out: at half the window
 * a task carries itself into a fresh one and drops its oldest tool results,
 * which genuinely removes them from the next request. That subtraction is a
 * fact about the machine rather than a decoration, and it is the only one this
 * product can honestly draw in red.
 *
 * **The window is named only when it was measured.** `ContextBudget` reads a
 * model's real loaded `num_ctx` from `/api/ps` and falls back to a constant
 * when it cannot — and the two must not look alike, because quoting a fallback
 * as a fact about somebody's machine is the failure `vram_bytes` refuses by
 * returning null rather than zero. Unmeasured, the share is simply not drawn.
 *
 * It renders nothing at all before the first exchange. A row of zeroes is a
 * claim that nothing was spent, which is different from not having spent
 * anything yet, and the distinction is the whole house style.
 */
import { useChatStore } from '@/stores/chatStore';

/** `12,431`, because a token count is read as a magnitude, not a quantity. */
const group = (n: number): string => n.toLocaleString('en-US');

export function TokenUsageBar() {
  const usage = useChatStore((s) => s.turnUsage);
  const isStreaming = useChatStore((s) => s.isStreaming);

  // Nothing spent and nothing in flight means nothing to say. Not a zero row:
  // see the note above.
  if (usage.added === 0 && usage.reclaimed === 0) return null;

  // Only when the window was actually read. An unmeasured limit is a constant
  // this component has no business quoting back.
  const share =
    usage.measured && usage.limit && usage.limit > 0
      ? Math.min(100, Math.round((usage.added / usage.limit) * 100))
      : null;

  const title = [
    `${group(usage.added)} tokens sent and generated this exchange`,
    usage.reclaimed > 0
      ? `${group(usage.reclaimed)} reclaimed when the task compacted at half the window`
      : null,
    share !== null ? `${share}% of this model's loaded ${group(usage.limit!)}-token window` : null,
  ]
    .filter(Boolean)
    .join('\n');

  return (
    <div
      className="mb-2 flex items-center gap-2 px-1 text-[11px] tabular-nums"
      title={title}
      aria-live="off"
    >
      <span aria-label={`${group(usage.added)} tokens added`} style={{ color: 'var(--color-added, #4ade80)' }}>
        +{group(usage.added)}
      </span>
      {usage.reclaimed > 0 && (
        <span
          aria-label={`${group(usage.reclaimed)} tokens reclaimed`}
          style={{ color: 'var(--color-removed, #f87171)' }}
        >
          −{group(usage.reclaimed)}
        </span>
      )}
      {share !== null && (
        <span style={{ color: 'var(--color-text-muted)' }}>
          {share}% of {group(usage.limit!)}
        </span>
      )}
      {isStreaming && (
        <span style={{ color: 'var(--color-text-muted)' }} aria-hidden="true">
          …
        </span>
      )}
    </div>
  );
}
