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
import { useState } from 'react';
import { AlertTriangle, ArrowRight, FileText, Library } from 'lucide-react';
import type { ChatNotice } from '../../stores/chatStore';
import type { WorkspaceId } from '@/runtime/shortcuts/registry';

const DESTINATIONS: Record<string, { node: WorkspaceId; label: string }> = {
  knowledge: { node: 'knowledge', label: 'Open Sources' },
  // A notice that names a switch the user can flip should be one click from
  // the switch. Search being off is the first case: telling someone their
  // answer is stale and leaving them to find the setting is half a disclosure.
  settings: { node: 'settings', label: 'Open Settings' },
};
//: Typed `WorkspaceId` rather than `string`, for the reason `LeftRail` types
//: its own map that way: a destination that is not a real node should fail to
//: compile rather than render a button that goes nowhere. Which is precisely
//: what this card did — see `ChatSurface`, where `onOpen` used to be wired to
//: a store nothing read.

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
  onOpen?: (node: WorkspaceId) => void;
  /** Turn web search on and ask the same question again.
   *
   *  Optional, so every existing caller and every test that renders a notice
   *  on its own keeps working; when it is absent the card falls back to the
   *  Settings link it has always shown. */
  onEnableSearch?: () => Promise<void>;
}

export default function NoticeCard({ notice, onOpen, onEnableSearch }: Props) {
  const destination = DESTINATIONS[notice.action];
  const { Icon, color } = TONES[notice.kind] ?? DEFAULT_TONE;

  // **Rule 7h, which this card was one click short of.** "Offer at the moment
  // of doubt; never make the user choose in advance" — and the search notice
  // was arriving at exactly the right moment with a link to a settings screen.
  // A person told their answer may be stale, mid-question, does not go to
  // Settings; they shrug and read the stale answer, and the disclosure has
  // taught them nothing except that Zaram is worse than a browser tab.
  //
  // The offer is not a weaker consent than the switch in Settings. It is the
  // same decision, made by the same person, at the moment they can actually
  // judge it — and the per-source grant `SearchReadGrant` enforces still runs
  // afterwards, so turning this on permits *searching*, not reading anything
  // it finds.
  const [phase, setPhase] = useState<'idle' | 'working' | 'failed'>('idle');
  const offersSearch = notice.kind === 'search' && Boolean(onEnableSearch);

  async function enableSearch() {
    if (!onEnableSearch) return;
    setPhase('working');
    try {
      await onEnableSearch();
      // **Back to idle, and this was a real defect.** The card lives in the
      // transcript, so it is still on screen after the retry — and without
      // this it sat there reading "Turning it on…" for the rest of the
      // session, over a question that had already been answered again.
      // Reported by the maintainer on the first press.
      setPhase('idle');
    } catch {
      // Named rather than silent: the button did nothing, and a control that
      // appears to work and does not is worse than one that says it failed.
      setPhase('failed');
    }
  }

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

        {offersSearch && (
          <>
            <button
              onClick={() => void enableSearch()}
              disabled={phase === 'working'}
              className="mt-1.5 text-[11px] flex items-center gap-1 disabled:opacity-50"
              style={{ color: 'var(--color-cyan-light)' }}
              data-testid="notice-enable-search"
            >
              {phase === 'working' ? 'Turning it on…' : 'Search the web and try again'}
              <ArrowRight size={10} />
            </button>
            {/* Said under the button, not behind it. Two things happen when
                this is pressed — search is turned on, and the search engine
                becomes a permitted destination — and the sentence names both,
                because the second is the rule-7j consent this press *is*. An
                offer whose disclosure covers half of what it does would be the
                same defect as the refusal it replaced. */}
            <p className="mt-1 text-[10px] leading-snug" style={{ color: 'var(--color-text-faint)' }}>
              {phase === 'failed'
                ? 'Zaram could not turn search on. It is in Settings under Privacy.'
                : 'Your question goes to a search engine, which is allowed from now on and ' +
                  'recorded in Activity. You can revoke it in Settings.'}
            </p>
          </>
        )}

        {!offersSearch && destination && onOpen && (
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
