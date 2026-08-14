/**
 * The controls that sit under a message: copy, and retry.
 *
 * What is here, and what is deliberately not
 * ------------------------------------------
 * Every chat product ships roughly the same row — copy, regenerate, edit,
 * thumbs up, thumbs down. Two of those five are refused here, and the refusals
 * are the interesting part.
 *
 * **No thumbs.** `CLAUDE.md` rule 7f: *do not build a feedback mechanism whose
 * action has no purpose other than giving feedback.* A thumbs-down conflates
 * "the fact was wrong", "the tone was wrong" and "you misunderstood me" into
 * one uninterpretable click, and Zaram already has a feedback mechanism that
 * is specific and acts on something — correcting or deleting the fact behind
 * the answer, which changes what the next answer says. Adding a thumb would
 * put a cheap gesture next to the real one and most people would take the
 * cheap one.
 *
 * **Copy takes the text a human would want**, which is not the text the model
 * produced. `[M1]` and `[S2]` are grounding markers; they mean nothing outside
 * Zaram and pasting them into an email is a small, avoidable embarrassment.
 * `stripCitationMarkers` is the same function the speech path uses, for the same
 * reason — there were three callers of that idea once and the one that had
 * been missed was the one that spoke the markers aloud. This is the fourth
 * caller and it uses the function rather than its own regex.
 *
 * **Retry re-asks the question; it does not "regenerate".** The distinction is
 * real: a regenerate button implies the same request produces a different
 * answer, and with recall in the loop the second answer is grounded in a Spine
 * that may have changed since the first. Re-sending the user's prompt is the
 * honest description of what happens, and it is what the label says.
 */
import { useState } from 'react';
import { Copy, Check, RotateCcw, Pencil } from 'lucide-react';
import { stripCitationMarkers } from '@/lib/markers';

/** How long the copied confirmation stays up. Long enough to be seen at a
 *  glance, short enough that it is gone before the next message arrives. */
const CONFIRM_MS = 1600;

function ActionButton({
  label,
  onClick,
  children,
  disabled,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className="inline-flex items-center gap-1 px-1.5 py-1 rounded-md text-[10px] text-slate-500 hover:text-slate-300 hover:bg-white/5 disabled:opacity-30 transition-colors"
    >
      {children}
    </button>
  );
}

export default function MessageActions({
  text,
  onRetry,
  onEdit,
  retryLabel = 'Ask again',
  align = 'left',
}: {
  /** The message body. Markers are stripped here, not by the caller. */
  text: string;
  /** Omitted where re-asking makes no sense — e.g. while a reply is streaming. */
  onRetry?: () => void;
  /**
   * Put this message back in the composer to be changed and sent again.
   *
   * Deliberately *not* an in-place edit of the message in the transcript. Every
   * other product rewrites history: the old prompt disappears, its answer is
   * replaced, and what you asked first is gone. That is fine where the reply is
   * the only artifact, and wrong here — a Zaram answer carries citations, and
   * facts may have entered the Spine because of the exchange. Silently deleting
   * the question that produced them would leave provenance pointing at
   * something the user can no longer see.
   *
   * So editing loads the text back into the composer and the original stays put.
   * The transcript remains a record of what was actually asked.
   */
  onEdit?: () => void;
  retryLabel?: string;
  align?: 'left' | 'right';
}) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    const clean = stripCitationMarkers(text).trim();
    try {
      await navigator.clipboard.writeText(clean);
      setCopied(true);
      window.setTimeout(() => setCopied(false), CONFIRM_MS);
    } catch {
      // Clipboard access can be refused — a page without focus, a locked-down
      // browser policy. Silently doing nothing would leave the user pressing a
      // button that appears broken, so the state says so rather than lying
      // with a tick. There is nothing to retry automatically.
      setCopied(false);
    }
  };

  return (
    <div
      className="flex items-center gap-0.5 mt-1"
      style={{ justifyContent: align === 'right' ? 'flex-end' : 'flex-start' }}
    >
      <ActionButton label={copied ? 'Copied' : 'Copy this message'} onClick={() => void copy()}>
        {copied ? (
          <>
            <Check size={11} style={{ color: 'var(--color-emerald)' }} />
            <span style={{ color: 'var(--color-emerald)' }}>Copied</span>
          </>
        ) : (
          <>
            <Copy size={11} />
            <span>Copy</span>
          </>
        )}
      </ActionButton>

      {onEdit && (
        <ActionButton label="Edit and send again" onClick={onEdit}>
          <Pencil size={11} />
          <span>Edit</span>
        </ActionButton>
      )}

      {onRetry && (
        <ActionButton label={retryLabel} onClick={onRetry}>
          <RotateCcw size={11} />
          <span>{retryLabel}</span>
        </ActionButton>
      )}
    </div>
  );
}
