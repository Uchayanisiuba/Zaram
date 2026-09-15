/**
 * The one notice that belongs on the sources line rather than in a banner.
 *
 * When recall surfaces a passage that reads like an instruction, Zaram quotes
 * it instead of obeying it and says so. Until 15 September 2026 it said so as
 * an amber warning triangle across the width of the reply — and that is the
 * wrong shape twice over.
 *
 * **It is not a warning.** Nothing went wrong and nothing is being asked of
 * the reader: the defence worked, and the sentence describes it working. An
 * amber triangle means *this may hurt you*, and `NoticeCard`'s own header
 * already argues what spending it on routine housekeeping costs — *"warning
 * the user about their own setting is how an indicator gets trained away, and
 * the amber one has real work to do."* This case arrived after that note and
 * fell through to the default tone, which is exactly how the argument gets
 * lost.
 *
 * **And it is about the sources.** It describes one of the passages already
 * counted on the line beneath the reply, so it belongs there — a quiet extra
 * segment beside *"4 sources · nothing left this device"*, opening into the
 * panel that holds the passage itself. Maintainer's call, 15 September 2026:
 * the diamond and the count carry it.
 *
 * **What it must not become is silent.** `core/untrusted.py` is explicit that
 * the scan reports rather than filters, *"because a filter that quietly
 * removes things trains nobody — the user never learns the document was
 * suspicious, which is the fact worth surfacing."* So this is a demotion in
 * loudness and never in reach: with citations on screen it rides the sources
 * line, and with none it stays a notice, in the neutral tone.
 */
import type { ChatNotice } from '../../stores/chatStore';

/** The backend's tag for it. One spelling, imported rather than retyped. */
export const QUOTED_KIND = 'untrusted';

/** The sources-line segment. Short, because the line is scanned, and the
 *  sentence itself is one click away in the panel. */
export const QUOTED_SEGMENT = 'one passage quoted, not acted on';

export interface SplitNotices {
  /** Everything that still renders as a card. */
  cards: ChatNotice[];
  /** The quoted-passage notice, when there was one. */
  quoted: ChatNotice | null;
}

/**
 * Separate the quoted-passage notice from the notices that stay cards.
 *
 * Returns the notice rather than a boolean so the caller keeps its wording —
 * the backend owns that sentence, and a second copy in the interface would be
 * the one that drifts.
 */
export function splitQuotedNotice(notices: ChatNotice[] | undefined): SplitNotices {
  if (!notices || notices.length === 0) return { cards: [], quoted: null };
  const quoted = notices.find((n) => n.kind === QUOTED_KIND) ?? null;
  return {
    cards: notices.filter((n) => n.kind !== QUOTED_KIND),
    quoted,
  };
}
