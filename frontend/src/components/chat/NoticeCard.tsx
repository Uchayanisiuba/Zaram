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
import { LOCAL_IS_FREE } from '@/lib/freeTier';
import {
  AlertTriangle,
  ArrowRight,
  Brain,
  FileText,
  Image as ImageIcon,
  Cpu,
  Library,
  ListChecks,
  MessageSquare,
  Quote,
  Search,
  Wrench,
} from 'lucide-react';
import type { ChatNotice } from '../../stores/chatStore';
import type { WorkspaceId } from '@/runtime/shortcuts/registry';

const DESTINATIONS: Record<string, { node: WorkspaceId; label: string }> = {
  knowledge: { node: 'knowledge', label: 'Open Sources' },
  // A notice that names a switch the user can flip should be one click from
  // the switch. Search being off is the first case: telling someone their
  // answer is stale and leaving them to find the setting is half a disclosure.
  settings: { node: 'settings', label: 'Open Settings' },
  // A contradiction between two stored facts is a question only the user can
  // settle, and Memory is where `correct()` lives. Without this entry the
  // notice renders the question and no way to answer it — which is the same
  // half-disclosure as telling someone search is off and leaving them to find
  // the switch.
  memory: { node: 'memory', label: 'Open Memory' },
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
  // A tool loop that stopped because it had read as much as the window allows.
  // Neutral for the same reason `domain` is: nothing went wrong, the model
  // spent its reading allowance, and an amber triangle over "here is what I
  // found so far" would train the warning away for the cases that need it.
  tool_loop: { Icon: Wrench, color: 'var(--color-text-muted, #94a3b8)' },
  // The conversation outgrew the model's window, so the earliest exchanges are
  // no longer in front of it. Neutral for the same reason `tool_loop` is:
  // nothing failed, a bounded window was reached, and an amber triangle would
  // say something broke. `Brain` is the icon the Memory node already wears, so
  // the notice reads as being about memory without needing to say so twice.
  memory: { Icon: Brain, color: 'var(--color-text-muted, #94a3b8)' },
  // A recalled passage that reads like an instruction and was quoted rather
  // than obeyed. Neutral, and the reasoning is the header's own, arriving
  // through a fifth case: nothing went wrong, the defence worked, and an
  // amber triangle over "this was handled" spends the warning on a reader
  // who is not in any danger. Normally this does not render as a card at
  // all — it rides the sources line (`quotedNotice.ts`) — and this tone is
  // for the answer that cited nothing, where there is no line to ride.
  untrusted: { Icon: Quote, color: 'var(--color-text-muted, #94a3b8)' },
  // **Five more, audited together on 15 September 2026**, after the
  // maintainer asked why a caution mark was on something that endangers
  // nobody. Every one of these had been arriving as an amber triangle purely
  // because it was added to the backend after this map — which is how the
  // argument at the top of this file gets lost one kind at a time.
  //
  // The plan is waiting on a person to read it and press Go. Nothing is
  // wrong; the pause is the product working.
  plan: { Icon: ListChecks, color: 'var(--color-text-muted, #94a3b8)' },
  // "3 servers are available for this question." A statement of what is
  // attached, and the least alarming sentence in the product.
  tools: { Icon: Wrench, color: 'var(--color-text-muted, #94a3b8)' },
  // Something the model said between steps.
  step: { Icon: MessageSquare, color: 'var(--color-text-muted, #94a3b8)' },
  // A model swap. Housekeeping about VRAM the user can do nothing about, and
  // the same call `IMAGES_HOUSEKEEPING` makes below for the same reason.
  resident: { Icon: Cpu, color: 'var(--color-text-muted, #94a3b8)' },
  // Search is off, so the answer may be stale. A disabled capability stated
  // plainly, which `CLAUDE.md` requires — and it carries a button to turn it
  // on, which is what makes it an offer rather than a warning.
  search: { Icon: Search, color: 'var(--color-text-muted, #94a3b8)' },
};

// **What keeps the amber triangle**, so the audit above is a decision rather
// than a sweep: `ingest` — a file the user added that gave nothing back, the
// founding case this component was written for — and `stuck`, which offers to
// send the question and the files Zaram read to a cloud model. One is data the
// user believes they have and do not; the other is bytes about to leave the
// machine. Those are the two that earn it, and an unrecognised kind keeps it
// too, because understating a problem is the worse of the two failures.

const DEFAULT_TONE = { Icon: AlertTriangle, color: 'var(--color-amber, #d97706)' };

// The images runtime speaks in two registers under one kind, and the action
// tells them apart. "Drawing this unloads qwen3-14b first" names no
// destination: it is housekeeping the user can do nothing about and should
// not be warned over. "TabbyAPI is holding the card and Zaram cannot unload
// it" points at Settings, and that one *is* a refusal — the amber default is
// right for it. Keyed on the action rather than on a second kind so the
// backend's one tag stays one tag.
const IMAGES_HOUSEKEEPING = { Icon: ImageIcon, color: 'var(--color-text-muted, #94a3b8)' };

function toneFor(notice: ChatNotice) {
  if (notice.kind === 'images' && !notice.action) return IMAGES_HOUSEKEEPING;
  return TONES[notice.kind] ?? DEFAULT_TONE;
}

interface Props {
  notice: ChatNotice;
  onOpen?: (node: WorkspaceId) => void;
  /** Turn web search on and ask the same question again.
   *
   *  Optional, so every existing caller and every test that renders a notice
   *  on its own keeps working; when it is absent the card falls back to the
   *  Settings link it has always shown. */
  onEnableSearch?: () => Promise<void>;
  /** Pick the stopped task up where it left off.
   *
   *  Optional like `onEnableSearch`, so a card rendered on its own still
   *  works. The offer only appears when the backend sent `action: "continue"`,
   *  which it does when a tool loop stopped with work left — never on a loop
   *  that finished, because there would be nothing to continue. */
  onContinue?: () => void;
  /** Ask the same question again with the named cloud model — the offer the
   *  backend makes when the project's tests failed twice on the local one.
   *
   *  `CLAUDE.md`: difficulty is routed by reaction, not prediction, and the
   *  reaction is *one offer under the reply, for this step, never a mode*.
   *  The card's own sentence says what leaves; pressing it is the rule-7j
   *  decision, and the egress gate and log still run on the way out. */
  onTryCloud?: (model: string) => void;
  /** Open the folder the person named as a coding project and ask again.
   *  The "open-project" offer — `docs/PLAN.md` F1, rule 7h: the project is
   *  created from the sentence, at the moment it is wanted, never required
   *  in advance. Optional like the others. */
  onOpenProject?: (path: string, name: string) => Promise<void> | void;
}

export default function NoticeCard({ notice, onOpen, onEnableSearch, onContinue, onTryCloud, onOpenProject }: Props) {
  // **"14 attached tools are available for this question" is not shown.**
  // Available means offered — the definitions were put in front of the
  // model — not called, and a person reading it asked whether all fourteen
  // ran (13 September). The disclosure the line existed for is already made
  // better by the tool-call rows: each call, as it happens, with its server
  // named. That is what every comparable product shows and nothing else.
  // The event still arrives, because `orbActivity` reads its `servers` to
  // report *coding* before the first token; only the card is withheld.
  if (notice.kind === 'tools') return null;

  const destination = DESTINATIONS[notice.action];
  const tone = toneFor(notice);
  const { Icon, color } = tone;
  const offersContinue = notice.action === 'continue' && Boolean(onContinue);
  const offersCloud = notice.action === 'cloud' && Boolean(notice.model) && Boolean(onTryCloud);
  // `go` is offered by the plan card's own button, above; the notice carries
  // the sentence and nothing else, so one press exists rather than two.
  const isGo = notice.action === 'go';
  const offersProject =
    notice.action === 'open-project' && Boolean(notice.path) && Boolean(onOpenProject);

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
      className="mt-2 rounded-lg px-3 py-2.5 flex items-start gap-2.5 surface"
      data-testid="chat-notice"
      data-kind={notice.kind || 'default'}
      data-tone={tone === DEFAULT_TONE ? 'warning' : 'neutral'}
    >
      <Icon size={13} className="mt-0.5 shrink-0" style={{ color }} />
      <div className="flex-1 min-w-0">
        <p className="text-xs leading-relaxed text-slate-300">{notice.content}</p>

        {offersSearch && (
          <>
            <button
              onClick={() => void enableSearch()}
              disabled={phase === 'working'}
              className="mt-1.5 text-xs flex items-center gap-1 disabled:opacity-50"
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
            <p className="mt-1 text-xs leading-snug" style={{ color: 'var(--color-text-faint)' }}>
              {phase === 'failed'
                ? 'Zaram could not turn search on. It is in Settings under Privacy.'
                : 'Your question goes to a search engine, which is allowed from now on and ' +
                  'recorded in Activity. You can revoke it in Settings.'}
            </p>
          </>
        )}

        {offersContinue && (
          <button
            onClick={onContinue}
            className="mt-1.5 text-xs flex items-center gap-1"
            style={{ color: 'var(--color-cyan-light)' }}
            data-testid="notice-continue"
          >
            Continue
            <ArrowRight size={10} />
          </button>
        )}

        {offersCloud && (
          <button
            onClick={() => onTryCloud?.(notice.model as string)}
            className="mt-1.5 text-xs flex items-center gap-1"
            style={{ color: 'var(--color-cyan-light)' }}
            data-testid="notice-try-cloud"
          >
            Try this step with {notice.model}
            <ArrowRight size={10} />
          </button>
        )}
        {/* The offer to leave the machine says, in the same breath, what
            staying costs: nothing. See `lib/freeTier`. */}
        {offersCloud && (
          <p className="mt-1 text-xs leading-relaxed" style={{ color: 'var(--color-text-faint)' }} data-testid="notice-local-free">
            {LOCAL_IS_FREE}
          </p>
        )}

        {offersProject && (
          <button
            onClick={() => void onOpenProject?.(notice.path as string, notice.name || 'Project')}
            className="mt-1.5 text-xs flex items-center gap-1"
            style={{ color: 'var(--color-cyan-light)' }}
            data-testid="notice-open-project"
          >
            Open {notice.name || 'it'} as a coding project
            <ArrowRight size={10} />
          </button>
        )}

        {!offersSearch && !offersContinue && !offersCloud && !isGo && !offersProject && destination && onOpen && (
          <button
            onClick={() => onOpen(destination.node)}
            className="mt-1.5 text-xs flex items-center gap-1"
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
