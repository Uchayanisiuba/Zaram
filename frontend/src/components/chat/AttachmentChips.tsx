/**
 * What is attached to the message you are about to send.
 *
 * **The size is on the chip, not behind it.** A document's length is what
 * decides whether Zaram reads it whole or searches it, and that decision
 * arrives in the reply as a notice. Showing "12 pages" before the question is
 * asked is what makes "too long to read at once" read as a consequence rather
 * than as a surprise.
 *
 * **Keep is an offer, never a gate.** Rule 7d: a file dropped into a
 * conversation is working state, and entering the Spine is a separate
 * decision. So the file is usable immediately and `Keep` sits beside it for
 * afterwards — asking first would make every question about a document a
 * commitment to remember it for ever, which is how a knowledge base fills with
 * things somebody looked at once.
 *
 * **A refusal is a row here, not a toast.** Dropping four files of which one
 * is a screenshot attaches three, and the fourth has to say why somewhere that
 * does not disappear on a timer — the user is about to ask a question whose
 * answer depends on what is actually in scope.
 */
import { useState } from 'react';
import { Check, FileText, Loader2, Paperclip, X } from 'lucide-react';

import {
  attachmentSize,
  type ChatAttachment,
  type RefusedAttachment,
} from '@/services/attachmentsClient';

interface Props {
  attachments: ChatAttachment[];
  refused: RefusedAttachment[];
  /** Ids already added to Knowledge, so `Keep` can report rather than repeat. */
  kept: string[];
  busy: string | null;
  onDetach: (id: string) => void;
  onKeep: (id: string) => void;
  onDismissRefusal: (name: string) => void;
}

export default function AttachmentChips({
  attachments,
  refused,
  kept,
  busy,
  onDetach,
  onKeep,
  onDismissRefusal,
}: Props) {
  const [hovered, setHovered] = useState<string | null>(null);

  if (attachments.length === 0 && refused.length === 0) return null;

  return (
    <div className="px-1 pb-2 flex flex-col gap-1.5">
      {attachments.map((item) => {
        const isKept = kept.includes(item.id);
        const working = busy === item.id;
        return (
          <div
            key={item.id}
            onMouseEnter={() => setHovered(item.id)}
            onMouseLeave={() => setHovered(null)}
            className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-[11px]"
            style={{
              background: 'var(--color-glass)',
              border: '1px solid var(--color-border-subtle)',
            }}
          >
            <FileText size={13} style={{ color: 'var(--color-cyan-light)', flexShrink: 0 }} />
            <span
              className="truncate"
              style={{ color: 'var(--color-text)', maxWidth: '16rem' }}
              title={item.name}
            >
              {item.name}
            </span>
            {/* Measured by the parser. The unit is pages where the format has
                them, because that is the size a person can picture. */}
            <span style={{ color: 'var(--color-text-muted)', flexShrink: 0 }}>
              {attachmentSize(item)}
            </span>

            <div className="ml-auto flex items-center gap-1" style={{ flexShrink: 0 }}>
              {isKept ? (
                // Reports rather than offering again. "Keep" on something
                // already kept would either duplicate the source or silently
                // do nothing, and both teach the user not to trust the button.
                <span
                  className="flex items-center gap-1 px-1.5"
                  style={{ color: 'var(--color-emerald)' }}
                >
                  <Check size={12} />
                  In Knowledge
                </span>
              ) : (
                <button
                  onClick={() => onKeep(item.id)}
                  disabled={working}
                  className="px-1.5 py-0.5 rounded transition-colors hover:bg-white/5 disabled:opacity-40"
                  style={{ color: 'var(--color-text-muted)' }}
                  title="Add this to Knowledge so Zaram remembers it"
                >
                  {working ? <Loader2 size={12} className="animate-spin" /> : 'Keep'}
                </button>
              )}
              <button
                onClick={() => onDetach(item.id)}
                aria-label={`Remove ${item.name}`}
                className="p-0.5 rounded transition-colors hover:bg-white/5"
                style={{ opacity: hovered === item.id ? 1 : 0.4 }}
              >
                <X size={12} style={{ color: 'var(--color-text-muted)' }} />
              </button>
            </div>
          </div>
        );
      })}

      {refused.map((item) => (
        <div
          key={item.name}
          className="flex items-start gap-2 rounded-lg px-2.5 py-1.5 text-[11px]"
          style={{
            background: 'var(--color-glass)',
            border: '1px solid var(--color-amber, #d97706)',
          }}
        >
          <Paperclip
            size={13}
            style={{ color: 'var(--color-amber, #d97706)', flexShrink: 0, marginTop: 1 }}
          />
          <span className="leading-relaxed" style={{ color: 'var(--color-text-muted)' }}>
            {/* The backend's sentence, verbatim. It knows why — that this is an
                image Zaram cannot read yet, or which formats it can read — and
                rewriting it here would produce a second, vaguer copy. */}
            {item.reason}
          </span>
          <button
            onClick={() => onDismissRefusal(item.name)}
            aria-label={`Dismiss ${item.name}`}
            className="ml-auto p-0.5 rounded transition-colors hover:bg-white/5"
            style={{ flexShrink: 0 }}
          >
            <X size={12} style={{ color: 'var(--color-text-muted)' }} />
          </button>
        </div>
      ))}
    </div>
  );
}
