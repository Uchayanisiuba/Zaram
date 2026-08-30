/**
 * Inline citation chips and the summary line beneath a reply.
 *
 * `docs/UI-SPEC.md` → Citations. The one idea everything here follows from:
 * **a citation that tells you whether an answer cost you privacy is the
 * product's thesis at the sentence level.**
 *
 * Division of labour, and these must not be collapsed:
 * - **chips** — what mattered, attached to the prose
 * - **the summary line** — the egress split, at a glance
 * - **the panel** — everything, including what was recalled and not cited
 *
 * **Colour encodes egress, not category.** Cyan for anything that stayed,
 * violet for anything that left — the same two colours the orb uses for local
 * versus cloud. One meaning reused, so it needs no legend.
 */
import { FileText, Diamond, Globe } from 'lucide-react';

import { type ChatSource, sourceHost, sourceLeftDevice } from '@/services/chatClient';

/** Icon per kind. The kind is *what* it is; the colour is whether it left. */
const KIND_ICON = {
  document: FileText,
  memory: Diamond,
  web: Globe,
} as const;

const KIND_LABEL = {
  document: 'From one of your files',
  memory: 'A fact Zaram remembered',
  web: 'From the web — this left your machine',
} as const;

export function CitationChip({
  source,
  onOpen,
  forgotten = false,
}: {
  source: ChatSource;
  onOpen: (source: ChatSource, el: HTMLElement) => void;
  forgotten?: boolean;
}) {
  const left = sourceLeftDevice(source);
  const Icon = KIND_ICON[source.kind];

  // The site, on the chip, for a web source only.
  //
  // **Four web citations used to render as four identical globes**, and the
  // one thing that tells them apart — who published the page — was reachable
  // only by opening the panel on each in turn. A row of sources is scanned,
  // not read, and a glyph that is the same for every entry carries nothing.
  //
  // Text rather than a favicon, and that is a decision rather than a stopgap.
  // A favicon is fetched from the site, which is a request `EgressGate`
  // structurally cannot see — `check-no-remote-assets.mjs` bans exactly that —
  // and it would fire on every *render*, so reopening a conversation next week
  // would ping the publisher again. The domain says more anyway: a name is
  // legible where a 16px mark is a guess, and it does not lend a content farm
  // the authority of a nice logo.
  const host = sourceHost(source);
  const label = host ? `${KIND_LABEL[source.kind]} — ${host}` : KIND_LABEL[source.kind];

  // Never render a chip that is not clickable. Citing without linking fails
  // the only task a citation exists for — checking it — and for this product a
  // decorative citation is worse than none.
  return (
    <button
      type="button"
      onClick={(e) => onOpen(source, e.currentTarget)}
      title={`${label}${forgotten ? ' — forgotten' : ''}`}
      aria-label={`Source ${source.number ?? ''}: ${label}`}
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full border text-[10px] leading-none align-baseline transition-colors hover:bg-white/5"
      style={{
        borderColor: left ? 'rgba(168,85,247,0.45)' : 'rgba(34,211,238,0.40)',
        color: left ? 'rgb(196,152,252)' : 'rgb(120,220,240)',
        textDecoration: forgotten ? 'line-through' : 'none',
        opacity: forgotten ? 0.55 : 1,
      }}
    >
      <Icon size={9} aria-hidden />
      {source.number != null && <span>{source.number}</span>}
      {/* Capped, and truncated from the *end*, because a domain is read
          left to right and its first label is the part that identifies it:
          "logupdateafrica…" is recognisable and "…africa.com" is not. Set at
          the same size as the number so a long name cannot make one chip
          tower over its neighbours in a wrapped row. */}
      {host && (
        <span
          className="max-w-[11rem] truncate"
          style={{ opacity: 0.85 }}
        >
          {host}
        </span>
      )}
    </button>
  );
}

export default function CitationSummary({
  sources,
  deleted,
  onOpenPanel,
  onOpenSource,
}: {
  sources: ChatSource[];
  deleted: Set<string>;
  onOpenPanel: (el: HTMLElement) => void;
  onOpenSource: (source: ChatSource, el: HTMLElement) => void;
}) {
  const cited = sources.filter((s) => s.cited);
  const uncited = sources.length - cited.length;

  // Nothing cited, nothing shown. **Citations appear only where there is a
  // tangible connection to the user's files.**
  //
  // This reverses a deliberate earlier decision, and the reasoning it replaces
  // is worth keeping: the old comment argued that an empty state is a claim
  // about *absence*, which the user cannot infer from missing chips, and that a
  // visible no-sources state beats confident prose with hidden provenance. That
  // holds for a research question. It does not hold for "Hi" — the line
  // appeared under every greeting and small-talk turn, which taught the user to
  // stop reading it, and a provenance affordance nobody reads is worse than
  // none. Maintainer's call, 10 August 2026.
  //
  // Safe against rule 3, and not by luck: bytes that leave are disclosed
  // through `_search_provenance_events`, which is "always cited, never
  // thresholded". So `cited.length === 0` guarantees nothing left the device,
  // and this can never hide an egress. If that ever changes, this check has to
  // change with it — which is why the guarantee is named here rather than
  // assumed.
  //
  // Most of what this used to render is now prevented upstream: `RecallGate`
  // stops a conversational turn reaching the Spine at all, so there is usually
  // no source to hide.
  if (cited.length === 0) {
    return null;
  }

  const leftCount = cited.filter(sourceLeftDevice).length;

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      {cited.map((s, i) => (
        <CitationChip
          key={s.url ?? i}
          source={s}
          onOpen={onOpenSource}
          forgotten={s.url != null && deleted.has(s.url)}
        />
      ))}

      <button
        type="button"
        onClick={(e) => onOpenPanel(e.currentTarget)}
        className="text-[10px] text-slate-500 hover:text-slate-300 transition-colors rounded px-1 -mx-1"
      >
        {/* Leads with the split, deliberately. The egress count is what someone
            wants at a glance, and burying it after a total makes it look like
            an afterthought. */}
        {cited.length} source{cited.length === 1 ? '' : 's'}
        {leftCount > 0 ? (
          <span style={{ color: 'rgb(196,152,252)' }}>
            {' · '}
            {leftCount} sent to the web
          </span>
        ) : (
          <span className="text-slate-600">{' · nothing left this device'}</span>
        )}
        {/* Named rather than hidden. The gap between what was recalled and what
            was cited is the whole reason there are two thresholds, and it is
            only arguable if it is visible. */}
        {uncited > 0 && (
          <span className="text-slate-600">
            {' · '}
            {uncited} recalled, not cited
          </span>
        )}
      </button>
    </div>
  );
}
