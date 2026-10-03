/**
 * One searchable model list, used by Settings and by the conversation chip.
 *
 * **Why it had to stop being a `<select>`.** Settings listed every model in a
 * native `select`, which cannot be typed into and cannot carry a mark — its
 * own comment says so: *"a native `option` cannot be styled portably and the
 * text is the one carrier that always survives."* That was a fair trade while
 * a provider meant five models. OpenRouter alone returns several hundred, and
 * scrolling a flat list of several hundred to find one is not a picker, it is
 * a filing cabinet. Reported 3 October 2026 as *"it's currently a drag to
 * navigate"*.
 *
 * **Two surfaces, one list, because they are one decision.** The chip beside
 * the composer and the field in Settings were already two renderings of
 * "which model answers", and they had drifted: the chip never marked a free
 * model at all, and Settings marked it in prose a native option forced it to.
 * A person who learns the picker in one place should not have to learn it
 * again in the other.
 *
 * **The free mark is a badge *and* a sentence, and that is not redundancy.**
 * `CLAUDE.md` is explicit that naming the deal is a primary feature of the
 * picker, and that a label saying "free" alone is *the offer without the
 * deal*. So the badge is the affordance — it is what makes a free tier
 * findable in three hundred rows — and the data-policy line underneath is
 * what keeps it honest. Neither replaces the other. A bare green chip is
 * precisely the thing this product exists not to ship.
 *
 * **Search matches what a person can see plus what they might paste.** The
 * display name, the id and the provider: somebody who knows a model as
 * `nvidia/nemotron` should find it by typing that, and somebody who only
 * knows "nemotron" should find it too. Matching is case-insensitive and on
 * every whitespace-separated term, so "free nemotron" narrows rather than
 * failing — the two words a person actually has in mind.
 *
 * **Nothing here filters on consent, fit or capability.** Those are notes on
 * the row, exactly as before. `selectable_by_default` gates auto-routing, not
 * the user asking, and hiding a model somebody installed is the silent
 * failure this file's predecessor was careful to avoid.
 */
import { useMemo, useState } from 'react';
import { Check, Search, X } from 'lucide-react';

import type { DiscoveredModel } from '@/services/settingsClient';
import { describeDataPolicy } from '@/components/settings/AdvancedModelField';

/** Does this model match what was typed?
 *
 *  Every term must match somewhere, so terms narrow. Exported because this is
 *  the whole behaviour of the feature and it is worth asserting directly —
 *  driving the component for "does typing `nemo` hide the others" is a slower
 *  way of testing one predicate.
 */
export function matchesQuery(model: DiscoveredModel, query: string): boolean {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return true;
  // `free` is included deliberately: it is the word somebody types when they
  // are looking for a free model, and without it the badge is findable by eye
  // and not by keyboard — which defeats the point on a list this long.
  const hay = [
    model.displayName,
    model.id,
    model.provider,
    model.isFree === true ? 'free' : '',
    model.specialisation,
  ]
    .join(' ')
    .toLowerCase();
  return terms.every((term) => hay.includes(term));
}

/** The groups, in the order they are shown, after filtering.
 *
 *  Locality is the split because it is the one that changes what the choice
 *  *means* — a local model is a speed question and a cloud model is a
 *  question about where a document goes. Not re-using
 *  `groupModelsByLocality` from the Settings workspace: that returns labels
 *  written for a `<select>`'s optgroup, and importing a 2,000-line workspace
 *  into the composer's chip to get three strings is the wrong direction.
 */
export interface ModelGroupView {
  key: 'local' | 'cloud' | 'other';
  label: string;
  /** Whether a row in this group shows its data policy. Cloud only — it is
   *  the question there and noise beside a model that sends nothing. */
  policy: boolean;
  models: DiscoveredModel[];
}

export function groupForSearch(models: DiscoveredModel[]): ModelGroupView[] {
  const local = models.filter((m) => m.locality === 'local');
  const cloud = models.filter((m) => m.locality === 'cloud');
  const other = models.filter((m) => m.locality !== 'local' && m.locality !== 'cloud');

  const groups: ModelGroupView[] = [];
  if (local.length) {
    groups.push({ key: 'local', label: 'On this machine — nothing is sent', policy: false, models: local });
  }
  if (cloud.length) {
    groups.push({ key: 'cloud', label: 'Cloud — your prompt leaves this device', policy: true, models: cloud });
  }
  if (other.length) {
    // Named rather than hidden: if a locality Zaram does not recognise ever
    // appears, the user should see the model *and* see that we cannot vouch
    // for where it runs. Policy shown, because unknown is the answer here.
    groups.push({ key: 'other', label: 'Where this runs is not established', policy: true, models: other });
  }
  return groups;
}

/**
 * The deal in four words, for a row in a list of hundreds.
 *
 * `describeDataPolicy` writes a sentence, which is right where one model is
 * in question — `AdvancedModelField` resolves a typed name and has room to
 * explain. On a list it is a wall: 549 models on this machine, every row
 * repeating *"Terms unknown. Zaram will not route here on its own — choosing
 * it is your decision, and Activity records what went."* The tests passed
 * and the screen was unusable, which is why it was looked at.
 *
 * So the row gets the short form and the sentence becomes its `title`.
 * Nothing is dropped: `CLAUDE.md` requires the deal to be named beside the
 * model, and "trains on your prompts" names it. What it must never become is
 * silence, or a reassuring blank for the unknown case — `DataPolicy`'s own
 * docstring refuses to make unknown a member precisely because it would
 * start looking like a choice.
 */
export function shortDataPolicy(policy: string | null): string {
  switch (policy) {
    case 'never_leaves_device':
      return 'nothing is sent';
    case 'your_key_no_training':
      return 'your key · not trained on';
    case 'logged_and_trained_on':
      return 'logged · trains on your prompts';
    default:
      return 'terms unknown';
  }
}

/**
 * The free mark.
 *
 * Emerald because it is Zaram's own token for a good state, and because the
 * one colour it must not be is the violet `docs/UI-SPEC.md` assigns to cloud
 * — a free model is *usually* a cloud model, and a chip in the cloud colour
 * on a row that already says "your prompt leaves this device" would be
 * reporting locality twice and in a second vocabulary.
 *
 * `title` carries the deal for a pointer, and the row carries it in text for
 * everyone else. The badge alone is never the whole claim.
 */
export function FreeBadge() {
  return (
    <span
      title="Costs nothing per token. The provider logs your prompts, and most free tiers train on them — the line below says what this one does."
      className="shrink-0 rounded px-1 text-[10px] font-semibold uppercase tracking-wide leading-[1.4]"
      style={{
        background: 'rgba(16,185,129,0.16)',
        color: 'var(--color-emerald, #10b981)',
        border: '1px solid rgba(16,185,129,0.32)',
      }}
      data-testid="free-badge"
    >
      Free
    </span>
  );
}

export interface ModelSearchListProps {
  models: DiscoveredModel[];
  /** The currently chosen value, compared against whichever field `matchOn`
   *  names. Empty string means "Zaram decides". */
  value: string;
  /** Settings stores `model.id`; the composer chip stores `displayName`.
   *  Carried rather than normalised because changing what either one writes
   *  is a stored-settings migration, not a picker change. */
  matchOn: 'id' | 'displayName';
  onChoose: (value: string) => void;
  busy?: boolean;
  loading?: boolean;
  /** What "hand it back to Zaram" is called here. The two surfaces word it
   *  differently and both are right in their own sentence. */
  decideLabel: string;
  /** Shown when the user has typed nothing and there are no models at all. */
  empty?: string;
  /** Extra note under a row, for whatever the surface wants to say — the
   *  composer quotes the VRAM numbers, Settings quotes fit and tools. */
  noteFor?: (model: DiscoveredModel) => string | null;
}

/**
 * The search field, on its own, so both surfaces get the identical control.
 *
 * Lifted out rather than duplicated because the composer's chip keeps its own
 * two sections — it has a different and better empty state for each ("No
 * cloud provider is connected" is not the same news as "No chat model is
 * installed here") — while Settings renders one grouped list. Two layouts,
 * one way of typing into them.
 *
 * **It appears only once there is enough to search.** Below the threshold it
 * is a control that does nothing, and a row of chrome over four models is the
 * clutter the composer's own docstring argues against.
 */
export const SEARCH_APPEARS_ABOVE = 7;

export function ModelSearchBox({
  query,
  onQuery,
  total,
  shown,
}: {
  query: string;
  onQuery: (next: string) => void;
  /** How many there are to search. Decides whether this renders at all. */
  total: number;
  /** How many survive the current query, shown only while searching. */
  shown: number;
}) {
  if (total <= SEARCH_APPEARS_ABOVE) return null;
  const searching = query.trim() !== '';
  return (
    <div
      className="mb-2 flex items-center gap-1.5 rounded px-2 py-1"
      style={{ border: '1px solid var(--color-border-subtle, rgba(255,255,255,0.08))' }}
    >
      <Search size={11} aria-hidden style={{ color: 'var(--color-text-faint, #64748b)' }} />
      <input
        value={query}
        onChange={(event) => onQuery(event.target.value)}
        // Escape is deliberately left alone. In the composer the panel closes
        // on Escape and that is the behaviour people already have; swallowing
        // it here to clear a search box would make one key mean two things
        // depending on what has focus. The × is the clear.
        placeholder={`Search ${total} models…`}
        aria-label="Search models"
        autoComplete="off"
        spellCheck={false}
        data-testid="model-search-input"
        className="min-w-0 flex-1 bg-transparent text-xs outline-none"
        style={{ color: 'var(--color-text, #e2e4ee)' }}
      />
      {searching && (
        <>
          <span className="shrink-0 text-[10px]" style={{ color: 'var(--color-text-faint, #64748b)' }}>
            {shown}
          </span>
          <button
            type="button"
            onClick={() => onQuery('')}
            aria-label="Clear search"
            className="shrink-0 rounded p-0.5 hover:bg-white/10"
            style={{ color: 'var(--color-text-faint, #64748b)' }}
          >
            <X size={10} aria-hidden />
          </button>
        </>
      )}
    </div>
  );
}

export default function ModelSearchList({
  models,
  value,
  matchOn,
  onChoose,
  busy = false,
  loading = false,
  decideLabel,
  empty = 'No chat model was found.',
  noteFor,
}: ModelSearchListProps) {
  const [query, setQuery] = useState('');

  const groups = useMemo(() => {
    const matching = models.filter((model) => matchesQuery(model, query));
    return groupForSearch(matching);
  }, [models, query]);

  const shown = groups.reduce((n, g) => n + g.models.length, 0);

  return (
    <div data-testid="model-search-list">
      <ModelSearchBox query={query} onQuery={setQuery} total={models.length} shown={shown} />

      {loading && <p className="text-xs text-slate-600">Looking…</p>}

      {!loading && models.length === 0 && <p className="text-xs text-slate-600">{empty}</p>}

      {/* Searched, and nothing matched. Distinct from "no models": one is
          about the query and one is about the machine, and a single sentence
          covering both would be wrong in one of the two cases. */}
      {!loading && models.length > 0 && shown === 0 && (
        <p className="text-xs text-slate-600" data-testid="model-search-none">
          No model matches “{query.trim()}”.
        </p>
      )}

      {!loading &&
        groups.map((group) => (
          <div key={group.key} className="mb-2 last:mb-0">
            <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">{group.label}</p>
            {group.models.map((model) => {
              const chosen = value !== '' && value === model[matchOn];
              const note = noteFor?.(model) ?? null;
              return (
                <button
                  key={model.id}
                  type="button"
                  disabled={busy}
                  onClick={() => onChoose(chosen ? '' : model[matchOn])}
                  className="flex w-full items-start gap-1.5 rounded px-1.5 py-1 text-left transition-colors hover:bg-white/5 disabled:opacity-50"
                >
                  <Check
                    size={11}
                    className="mt-[3px] shrink-0"
                    style={{ color: chosen ? 'var(--color-cyan-light)' : 'transparent' }}
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5">
                      <span className="truncate text-xs text-slate-300">{model.displayName}</span>
                      {model.isFree === true && <FreeBadge />}
                    </span>
                    {note && <span className="block text-xs text-amber-400/80">{note}</span>}
                    {/* The deal, in words, under the badge. See the module
                        docstring: the badge makes a free tier findable and
                        this is what stops it being an advertisement.
                        Short on the row and whole on hover, because a list
                        of several hundred cannot carry a sentence each. */}
                    {group.policy && (
                      <span
                        className="block text-xs text-slate-500"
                        title={describeDataPolicy(model.dataPolicy)}
                      >
                        {shortDataPolicy(model.dataPolicy)}
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        ))}

      {/* Handing the choice back is a choice, so it is a row like any other —
          and it stays visible while searching, because a filtered list that
          hides the way out strands somebody who typed a typo. */}
      {!loading && models.length > 0 && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onChoose('')}
          className="flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-left transition-colors hover:bg-white/5 disabled:opacity-50"
        >
          <Check
            size={11}
            className="shrink-0"
            style={{ color: value === '' ? 'var(--color-cyan-light)' : 'transparent' }}
            aria-hidden
          />
          <span className="text-xs text-slate-500">{decideLabel}</span>
        </button>
      )}
    </div>
  );
}
