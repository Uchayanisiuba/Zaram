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
 *
 * **`kind` was carried and ignored, and that stopped being harmless with the
 * second case.** Every notice drew an amber warning triangle, which is right
 * for a file that could not be read and wrong for *"answering inside your
 * Investing domain"* — a statement about scope the user themselves chose.
 * Warning the user about their own setting is how an indicator gets trained
 * away, and the amber one has real work to do.
 */
import { AlertTriangle, ArrowRight, FileText, Library } from 'lucide-react';
import type { ChatNotice } from '../../stores/chatStore';

const DESTINATIONS: Record<string, { node: string; label: string }> = {
  knowledge: { node: 'knowledge', label: 'Open Sources' },
  // A notice that names a switch the user can flip should be one click from
  // the switch. Search being off is the first case: telling someone their
  // answer is stale and leaving them to find the setting is half a disclosure.
  settings: { node: 'settings', label: 'Open Settings' },
};

/** How a notice presents itself. Keyed on `kind`, which the backend sends.
 *
 *  The default is the warning, not the neutral form: an unrecognised kind is
 *  more likely to be something gone wrong than something routine, and under-
 *  stating a problem is the worse of the two failures. */
const TONES: Record<string, { Icon: typeof AlertTriangle; color: string }> = {
  domain: { Icon: Library, color: 'var(--color-text-muted, #94a3b8)' },
  // How much of an attached file the model actually saw. Neutral, because
  // "Read brief.txt in full" is the good outcome and the commonest one - an
  // amber warning triangle on it would be the exact failure the note above
  // describes, arriving through a third case.
  attachment: { Icon: FileText, color: 'var(--color-text-muted, #94a3b8)' },
};

const DEFAULT_TONE = { Icon: AlertTriangle, color: 'var(--color-amber, #d97706)' };

interface Props {
  notice: ChatNotice;
  onOpen?: (node: string) => void;
}

export default function NoticeCard({ notice, onOpen }: Props) {
  const destination = DESTINATIONS[notice.action];
  const { Icon, color } = TONES[notice.kind] ?? DEFAULT_TONE;

  return (
    <div
      className="mt-2 rounded-lg px-3 py-2.5 flex items-start gap-2.5"
      style={{
        border: '1px solid var(--color-border-subtle)',
        background: 'var(--color-glass)',
      }}
      data-testid="chat-notice"
      data-kind={notice.kind || 'default'}
    >
      <Icon size={13} className="mt-0.5 shrink-0" style={{ color }} />
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
