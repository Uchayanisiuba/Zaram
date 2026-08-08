/**
 * Something Zaram needs to say that the model did not say.
 *
 * The first and so far only case is ingest: a file that gave nothing back has
 * to be mentioned in the conversation *the first time it matters*, because
 * Knowledge showing it only helps a user who thinks to open Knowledge — and
 * someone whose document was silently skipped has no reason to.
 *
 * Deliberately not styled as a reply. Rendering it inside the assistant's text
 * would attribute it to the model, and the difference between "the model told
 * me this" and "the system is telling me this" is exactly the sort of thing
 * this product cannot afford to blur. It is also not an error: nothing failed
 * in this exchange, and red would train the user to dread a message that is
 * usually just housekeeping.
 */
import { AlertTriangle, ArrowRight } from 'lucide-react';
import type { ChatNotice } from '../../stores/chatStore';

const DESTINATIONS: Record<string, { node: string; label: string }> = {
  knowledge: { node: 'knowledge', label: 'Open Sources' },
};

interface Props {
  notice: ChatNotice;
  onOpen?: (node: string) => void;
}

export default function NoticeCard({ notice, onOpen }: Props) {
  const destination = DESTINATIONS[notice.action];

  return (
    <div
      className="mt-2 rounded-lg px-3 py-2.5 flex items-start gap-2.5"
      style={{
        border: '1px solid var(--color-border-subtle)',
        background: 'var(--color-glass)',
      }}
      data-testid="chat-notice"
    >
      <AlertTriangle
        size={13}
        className="mt-0.5 shrink-0"
        style={{ color: 'var(--color-amber, #d97706)' }}
      />
      <div className="flex-1 min-w-0">
        <p className="text-xs leading-relaxed text-slate-300">{notice.content}</p>
        {destination && onOpen && (
          <button
            onClick={() => onOpen(destination.node)}
            className="mt-1.5 text-[11px] flex items-center gap-1"
            style={{ color: 'var(--color-cyan-light)' }}
            data-testid="notice-action"
          >
            {destination.label}
            <ArrowRight size={10} />
          </button>
        )}
      </div>
    </div>
  );
}
