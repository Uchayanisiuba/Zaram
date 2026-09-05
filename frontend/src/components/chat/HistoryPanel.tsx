/**
 * Past conversations, on a lip at the edge that opens when you reach for it.
 *
 * **Not a seventh node, and that is a rule rather than a preference.**
 * CLAUDE.md fixes the navigation at six and says why: *"Conversation is not a
 * node. It is the shell."* History is history *of* the shell, so it lives
 * inside it. `LeftRail`'s `NAV_ICONS` is typed `Record<WorkspaceId, …>`
 * precisely so that adding a node fails to compile until someone has thought
 * about it.
 *
 * The edge-handle-that-opens-on-approach is the product's own vocabulary
 * already — it is how CLAUDE.md describes the ambient surface, *"a tab docked
 * to the screen edge that opens on hover"*. Reusing it here means one
 * interaction to learn rather than two.
 *
 * Three decisions, each fixing something a plain hover-flyout gets wrong:
 *
 * **Hover peeks; click pins.** A panel that closes when the pointer leaves is
 * fine for a glance and useless for the thing people actually do, which is
 * open it, read down the list, and think. Peek is translucent and
 * non-committal; a click commits it, and it then stays until dismissed.
 *
 * **Opening takes intent.** The left edge is crossed constantly on the way to
 * anything else, and a panel that fires on every pass is the classic flyout
 * irritation. `OPEN_DELAY_MS` is the difference between reaching for it and
 * travelling past it.
 *
 * **The lip is a control, not a decoration.** Hover does not exist on touch and
 * does not exist for a keyboard, so it is a real `button`: tappable, focusable,
 * and it opens on focus. A hint nobody can operate is worse than no hint.
 *
 * It carries a count, and the count is real — read from the store, absent until
 * it is known. CLAUDE.md: *"Never render invented values."*
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { MessageSquare, Trash2, X } from 'lucide-react';

import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { useChatStore } from '@/stores/chatStore';
import {
  deleteConversation,
  fetchConversations,
  type ConversationSummary,
} from '@/services/conversationsClient';

/** Long enough that crossing the edge does not open it; short enough that
 *  reaching for it does not feel gated. */
const OPEN_DELAY_MS = 260;

/** How long the pointer may be away before a peek closes. Covers the gap
 *  between the lip and the panel, and a hand that wobbles. */
const CLOSE_DELAY_MS = 220;

function dayLabel(updatedAt: number): string {
  const then = new Date(updatedAt * 1000);
  const now = new Date();
  const sameDay = then.toDateString() === now.toDateString();
  if (sameDay) return 'Today';

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (then.toDateString() === yesterday.toDateString()) return 'Yesterday';

  const days = Math.floor((now.getTime() - then.getTime()) / 86_400_000);
  if (days < 7) return 'This week';
  if (days < 30) return 'This month';
  return 'Earlier';
}

/** Group in order, keeping the store's recency sort inside each bucket. */
function groupByDay(rows: ConversationSummary[]): Array<[string, ConversationSummary[]]> {
  const groups: Array<[string, ConversationSummary[]]> = [];
  for (const row of rows) {
    const label = dayLabel(row.updatedAt);
    const last = groups[groups.length - 1];
    if (last && last[0] === label) last[1].push(row);
    else groups.push([label, [row]]);
  }
  return groups;
}

export default function HistoryPanel() {
  const reduced = useIsReducedMotion();
  const [rows, setRows] = useState<ConversationSummary[] | null>(null);
  const [peeking, setPeeking] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const openTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const currentId = useChatStore((s) => s.conversationId);
  const resume = useChatStore((s) => s.resumeConversation);
  const clear = useChatStore((s) => s.clear);

  const open = peeking || pinned;

  const load = useCallback(async () => {
    try {
      // Every conversation, not only the current project's. Someone reaching
      // for history is looking for something they may not remember the scope
      // of, and `undefined` asks a different question from `''` — see
      // `fetchConversations`.
      setRows(await fetchConversations());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'History could not be read.');
    }
  }, []);

  // Loaded when it opens rather than on mount: an ambient panel that fetches
  // on every page load spends a request on a surface nobody asked for.
  useEffect(() => {
    if (open && rows === null) void load();
  }, [open, rows, load]);

  // Refreshed when the conversation changes, because the list it shows just
  // became stale — a new conversation is missing from it, and the current one
  // has moved to the top.
  useEffect(() => {
    if (open) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentId]);

  const clearTimers = () => {
    if (openTimer.current) clearTimeout(openTimer.current);
    if (closeTimer.current) clearTimeout(closeTimer.current);
    openTimer.current = null;
    closeTimer.current = null;
  };

  useEffect(() => clearTimers, []);

  const beginPeek = () => {
    clearTimers();
    openTimer.current = setTimeout(() => setPeeking(true), OPEN_DELAY_MS);
  };

  const endPeek = () => {
    clearTimers();
    closeTimer.current = setTimeout(() => setPeeking(false), CLOSE_DELAY_MS);
  };

  const dismiss = () => {
    clearTimers();
    setPinned(false);
    setPeeking(false);
  };

  const onResume = async (id: string) => {
    dismiss();
    await resume(id);
  };

  const onDelete = async (id: string, event: React.MouseEvent) => {
    // The row is a button and so is this. Without stopping here, deleting a
    // conversation would also open it.
    event.stopPropagation();
    try {
      const { note: sentence } = await deleteConversation(id);
      // **Said, not assumed.** The backend's sentence explains that facts
      // Zaram remembered are still in Memory. Dropping it would leave the user
      // to guess whether a transcript delete also took their memory with it,
      // and the two are different requests.
      setNote(sentence);
      if (id === currentId) clear();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That conversation could not be deleted.');
    }
  };

  const transition = reduced ? 'none' : 'transform 0.22s ease, opacity 0.22s ease';

  return (
    <div
      className="fixed inset-y-0 left-0 z-[60] flex items-stretch pointer-events-none"
      onMouseLeave={endPeek}
    >
      {/* The lip. Always visible, always operable. */}
      <button
        type="button"
        aria-label={
          rows === null
            ? 'Past conversations'
            : `Past conversations (${rows.length})`
        }
        aria-expanded={open}
        className="pointer-events-auto self-center flex flex-col items-center justify-center gap-2 py-6"
        style={{
          width: 22,
          borderTopRightRadius: 10,
          borderBottomRightRadius: 10,
          border: '1px solid var(--color-border-subtle)',
          borderLeft: 'none',
          background: open ? 'var(--color-elevated)' : 'var(--color-glass)',
          backdropFilter: 'blur(8px)',
          cursor: 'pointer',
          transition,
          opacity: open ? 0 : 1,
        }}
        onMouseEnter={beginPeek}
        onFocus={() => setPeeking(true)}
        onClick={() => {
          clearTimers();
          setPinned(true);
          setPeeking(true);
        }}
      >
        <MessageSquare size={12} style={{ color: 'var(--color-text-muted)' }} />
        {/* A real count or nothing at all. An invented number on an indicator
            is worse than an empty one. */}
        {rows !== null && rows.length > 0 && (
          <span
            className="text-[9px]"
            style={{
              color: 'var(--color-text-muted)',
              fontFamily: 'var(--font-mono)',
              writingMode: 'vertical-rl',
            }}
          >
            {rows.length}
          </span>
        )}
      </button>

      {/* The panel. */}
      <aside
        aria-label="Past conversations"
        aria-hidden={!open}
        className="pointer-events-auto flex flex-col"
        style={{
          width: 264,
          marginLeft: -22,
          transform: open ? 'translateX(0)' : 'translateX(-100%)',
          opacity: open ? 1 : 0,
          // Peek is translucent and non-committal; a pinned panel is solid.
          // The difference is what tells you whether it will stay.
          background: pinned ? 'var(--color-surface)' : 'var(--color-elevated)',
          backdropFilter: 'blur(18px)',
          borderRight: '1px solid var(--color-border-subtle)',
          transition,
          visibility: open ? 'visible' : 'hidden',
        }}
        onMouseEnter={() => {
          clearTimers();
          setPeeking(true);
        }}
      >
        <header
          className="flex items-center justify-between px-3 py-2.5"
          style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
        >
          <span
            className="text-[10px] uppercase tracking-wider"
            style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-display)' }}
          >
            Conversations
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              className="text-[10px] px-1.5 py-0.5 rounded"
              style={{ color: 'var(--color-cyan)' }}
              onClick={() => {
                // Starting a new conversation does not delete the old one. It
                // is simply no longer the one being written into.
                clear();
                dismiss();
              }}
            >
              New
            </button>
            {pinned && (
              <button type="button" aria-label="Close history" onClick={dismiss}>
                <X size={12} style={{ color: 'var(--color-text-muted)' }} />
              </button>
            )}
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-1.5 py-1.5">
          {error && (
            <p className="text-[11px] px-2 py-2" style={{ color: 'var(--color-red)' }}>
              {error}
            </p>
          )}

          {/* Three states, told apart. "Not read yet" is not "none". */}
          {rows === null && !error && (
            <p className="text-[11px] px-2 py-2" style={{ color: 'var(--color-text-muted)' }}>
              Reading…
            </p>
          )}

          {rows !== null && rows.length === 0 && (
            <p
              className="text-[11px] px-2 py-2 leading-snug"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Nothing here yet. Conversations are kept on this machine as you have them.
            </p>
          )}

          {rows !== null &&
            groupByDay(rows).map(([label, group]) => (
              <div key={label} className="mb-2">
                <p
                  className="text-[9px] uppercase tracking-wider px-2 pt-1.5 pb-1"
                  style={{ color: 'var(--color-text-faint)' }}
                >
                  {label}
                </p>
                {group.map((row) => {
                  const active = row.id === currentId;
                  return (
                    <div
                      key={row.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => void onResume(row.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          void onResume(row.id);
                        }
                      }}
                      className="group flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer"
                      style={{
                        background: active ? 'var(--color-glass)' : 'transparent',
                        borderLeft: active
                          ? '2px solid var(--color-cyan)'
                          : '2px solid transparent',
                      }}
                    >
                      <span
                        className="flex-1 text-[11.5px] truncate"
                        style={{ color: active ? 'var(--color-text)' : 'var(--color-text-muted)' }}
                        title={row.title || 'Untitled'}
                      >
                        {row.title || 'Untitled'}
                      </span>
                      <button
                        type="button"
                        aria-label={`Delete ${row.title || 'this conversation'}`}
                        className="opacity-0 group-hover:opacity-100 focus:opacity-100"
                        onClick={(e) => void onDelete(row.id, e)}
                      >
                        <Trash2 size={11} style={{ color: 'var(--color-text-faint)' }} />
                      </button>
                    </div>
                  );
                })}
              </div>
            ))}
        </div>

        {note && (
          <p
            className="text-[10px] leading-snug px-3 py-2"
            style={{
              color: 'var(--color-text-muted)',
              borderTop: '1px solid var(--color-border-subtle)',
            }}
          >
            {note}
          </p>
        )}
      </aside>
    </div>
  );
}
