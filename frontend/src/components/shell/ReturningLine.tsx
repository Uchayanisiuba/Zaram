/**
 * One mono line under the orb, on a launch where there is something to say.
 *
 * `docs/UI-SPEC.md` 6h. Every segment is measured (`returningStore`), set in
 * the mono because each is a value the system reports, and each is a way in:
 * facts to Memory, projects to Project, the last conversation resumes, the
 * bytes to Activity. It is not a dashboard and does not become one — there is
 * no room in a line for a fifth thing, which is the point of a line.
 *
 * Dismissible for this launch with the × at the end, and skippable by doing
 * anything else: it intercepts nothing, sits under the ring, and the orb
 * above it is still the way in.
 */
import { X } from 'lucide-react';

import { useChatModeStore } from '@/stores/chatModeStore';
import { useChatStore } from '@/stores/chatStore';
import { useReturningStore, returningSegments, type Segment } from '@/stores/returningStore';
import type { WorkspaceId } from '@/runtime/shortcuts/registry';

export default function ReturningLine({ onNavigate }: { onNavigate: (id: WorkspaceId) => void }) {
  const returning = useReturningStore((s) => s.returning);
  const dismiss = useReturningStore((s) => s.dismiss);
  const segments = returning ? returningSegments(returning) : [];
  if (!segments.length) return null;

  const go = (segment: Segment) => {
    if (segment.target === 'resume' && segment.conversationId) {
      // Into the conversation it names, open on the landing — the same path
      // `HistoryPanel` takes, from one step further out.
      void useChatStore.getState().resumeConversation(segment.conversationId);
      useChatModeStore.getState().openChat();
      return;
    }
    if (segment.target !== 'resume') onNavigate(segment.target);
  };

  return (
    <p
      className="t-mono flex items-center gap-2 flex-wrap justify-center"
      data-testid="returning-line"
      style={{ pointerEvents: 'auto', margin: 0 }}
    >
      {segments.map((segment, i) => (
        <span key={segment.key} className="flex items-center gap-2">
          {i > 0 && <span aria-hidden style={{ color: 'var(--color-text-faint)' }}>·</span>}
          <button
            type="button"
            onClick={() => go(segment)}
            className="rounded-sm hover:underline underline-offset-4 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-cyan)]"
            style={{ color: 'inherit', background: 'none', border: 0, padding: 0, font: 'inherit', cursor: 'pointer' }}
            data-testid={`returning-${segment.key}`}
          >
            {segment.text}
          </button>
        </span>
      ))}
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss"
        className="ml-1 rounded-sm opacity-60 hover:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-cyan)]"
        style={{ color: 'inherit', background: 'none', border: 0, padding: 2, cursor: 'pointer' }}
      >
        <X size={12} aria-hidden />
      </button>
    </p>
  );
}
