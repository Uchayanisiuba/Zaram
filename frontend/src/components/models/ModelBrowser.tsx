/**
 * Choosing a model to download.
 *
 * Asked for 4 October 2026 with a screenshot of LM Studio's model browser,
 * and a second one of its empty state: *"when the user opens Zaram for the
 * first time and has no model ... users are able to click on the download
 * models button and select relevant models for their PC."*
 *
 * What this is not
 * ----------------
 * **Not a list of filenames with a size column.** `CLAUDE.md` is explicit
 * that the target user is not technical and that no model filenames belong
 * in the primary path. The name is here because it is what you type into
 * Ollama and what every other tool shows, but it is the *quiet* line — the
 * loud one is the manifest's own sentence about why you would want it,
 * written by a person.
 *
 * **Not a filter.** Models too large for this machine are listed and
 * greyed, never hidden. The pack catalogue already makes that argument,
 * and *"disabled capabilities are visible, not silent"* would be false on
 * the one screen whose whole subject is capability. Somebody deciding
 * whether to buy a card has a reason to see the row they cannot use.
 *
 * Three states per row, and they are different sentences
 * ------------------------------------------------------
 * *Installed* — nothing to do, this is a choice in Settings. *Fits* — a
 * download, with its price. *Too large* — shown, with the reason, and no
 * button, because offering one that cannot work is the shape of a product
 * that looks broken.
 *
 * And a fourth that is not a state: `fits === null`, the machine Zaram
 * could not measure. Apple and DirectML report no VRAM. Rendering that as
 * "too large" greys out the entire catalogue on a Mac; rendering it as
 * "fits" promises something nobody measured. It says so instead.
 */
import { useCallback, useEffect, useState } from 'react';
import { Check, Download, Loader2, Search } from 'lucide-react';

import {
  fetchModelCatalogue,
  gigabytes,
  type CatalogueModel,
} from '@/services/modelCatalogueClient';
import { pullRecommendedModel, type PullEvent } from '@/services/pullClient';

interface Props {
  /** A model finished downloading, so readiness should be asked again. */
  onInstalled?: () => void;
}

type Pulling = { name: string; stage: string; completed: number; total: number } | null;

export default function ModelBrowser({ onInstalled }: Props) {
  const [models, setModels] = useState<CatalogueModel[]>([]);
  const [budget, setBudget] = useState<number | null>(null);
  const [generated, setGenerated] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState('');
  const [pulling, setPulling] = useState<Pulling>(null);
  const [failure, setFailure] = useState('');
  const [reached, setReached] = useState(true);

  const load = useCallback(async () => {
    const catalogue = await fetchModelCatalogue();
    setReached(catalogue.outcome === 'ok');
    setModels(catalogue.models);
    setBudget(catalogue.budget_bytes);
    setGenerated(catalogue.generated);
    setLoaded(true);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function download(model: CatalogueModel) {
    setFailure('');
    setPulling({ name: model.name, stage: 'Starting', completed: 0, total: 0 });
    try {
      await pullRecommendedModel(
        (event: PullEvent) => {
          if (event.error) {
            setFailure(event.error);
            setPulling(null);
            return;
          }
          if (event.done) {
            setPulling(null);
            void load();
            onInstalled?.();
            return;
          }
          setPulling((was) =>
            was
              ? {
                  ...was,
                  stage: event.stage ?? was.stage,
                  // The pull's own arithmetic, never the manifest's. The
                  // quoted size is approximate and dated; counting against
                  // it produces a bar that reaches 103% or stalls at 96%,
                  // and a bar that lies about the end cannot be told from
                  // a stall.
                  completed: event.completed ?? was.completed,
                  total: event.total ?? was.total,
                }
              : was,
          );
        },
        undefined,
        model.name,
      );
    } catch (error) {
      setFailure(error instanceof Error ? error.message : 'That download could not start.');
      setPulling(null);
    }
  }

  const needle = query.trim().toLowerCase();
  const shown = needle
    ? models.filter(
        (m) =>
          m.name.toLowerCase().includes(needle) || m.why.toLowerCase().includes(needle),
      )
    : models;

  return (
    <div className="flex h-full flex-col" data-testid="model-browser">
      <div className="relative mb-3">
        <Search
          size={14}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
          style={{ color: 'var(--color-text-faint)' }}
          aria-hidden
        />
        <input
          data-testid="model-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search models"
          spellCheck={false}
          className="w-full rounded-lg py-2 pl-9 pr-3 text-sm outline-none"
          style={{
            background: 'var(--color-glass)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
          }}
        />
      </div>

      {failure && (
        <p
          data-testid="model-browser-error"
          className="mb-3 rounded-lg px-3 py-2 text-xs"
          style={{
            background: 'rgba(180,83,9,0.12)',
            border: '1px solid rgba(180,83,9,0.3)',
            color: 'var(--color-amber-light, #fcd34d)',
          }}
        >
          {/* A download that dies at 80% on a metered connection is the
              worst moment in this product to be vague. */}
          {failure} The button is still there if you want to try again.
        </p>
      )}

      <ul className="min-h-0 flex-1 space-y-2 overflow-auto">
        {shown.map((model) => {
          const busy = pulling?.name === model.name;
          const tooLarge = model.fits === false;
          return (
            <li
              key={model.name}
              data-testid={`model-${model.name}`}
              className="rounded-xl px-4 py-3"
              style={{
                background: 'var(--color-glass)',
                border: '1px solid var(--color-border-subtle)',
                // Greyed, not hidden.
                opacity: tooLarge ? 0.55 : 1,
              }}
            >
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm" style={{ color: 'var(--color-text)' }}>
                    {model.why}
                  </p>
                  <p
                    className="mt-1 truncate text-xs"
                    style={{
                      color: 'var(--color-text-faint)',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {model.name} · {gigabytes(model.size_bytes)}
                  </p>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  {model.recommended && !model.installed && (
                    <span
                      data-testid={`suggested-${model.name}`}
                      className="rounded-full px-2 py-0.5 text-[11px]"
                      style={{
                        border: '1px solid var(--color-cyan)',
                        color: 'var(--color-cyan-light)',
                      }}
                    >
                      suggested
                    </span>
                  )}
                  {model.installed ? (
                    <span
                      data-testid={`installed-${model.name}`}
                      className="flex items-center gap-1 text-xs"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      <Check size={13} aria-hidden /> installed
                    </span>
                  ) : tooLarge ? (
                    // No button. Offering one that cannot work is the
                    // shape of a product that looks broken.
                    <span
                      data-testid={`too-large-${model.name}`}
                      className="text-xs"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      needs more memory than this machine has
                    </span>
                  ) : (
                    <button
                      type="button"
                      data-testid={`download-${model.name}`}
                      disabled={!!pulling}
                      onClick={() => void download(model)}
                      className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs disabled:opacity-40"
                      style={{
                        border: '1px solid var(--color-border)',
                        color: 'var(--color-text)',
                      }}
                    >
                      {busy ? (
                        <Loader2 size={13} className="animate-spin" aria-hidden />
                      ) : (
                        <Download size={13} aria-hidden />
                      )}
                      {busy ? 'Downloading' : gigabytes(model.size_bytes)}
                    </button>
                  )}
                </div>
              </div>

              {busy && pulling && (
                <div className="mt-3">
                  <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    {pulling.stage}
                    {pulling.total > 0 &&
                      ` — ${gigabytes(pulling.completed)} of ${gigabytes(pulling.total)}`}
                  </p>
                  <div
                    className="mt-1.5 h-1 overflow-hidden rounded-full"
                    style={{ background: 'var(--color-border-subtle)' }}
                  >
                    <div
                      data-testid="pull-progress"
                      className="h-full rounded-full transition-all"
                      style={{
                        width: pulling.total
                          ? `${Math.min(100, (pulling.completed / pulling.total) * 100)}%`
                          : '0%',
                        background: 'var(--color-cyan)',
                      }}
                    />
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {loaded && shown.length === 0 && (
        <p
          data-testid="no-models"
          className="py-8 text-center text-sm"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {models.length > 0
            ? `Nothing matches “${query}”.`
            : reached
              ? 'Zaram’s list has nothing to offer for this machine. Everything already installed still works.'
              : 'Zaram could not reach its own backend, so there is no list to show. Everything already installed still works.'}
        </p>
      )}

      <p className="mt-3 text-xs" style={{ color: 'var(--color-text-faint)' }}>
        {/* The date is required to be visible: a recommendation is only as
            current as the list it came from. And the budget is said in the
            same breath, because that is what the greying is based on. */}
        {budget === null
          ? 'Zaram could not measure this machine’s graphics memory, so nothing here is marked as fitting or not.'
          : `Room for about ${gigabytes(budget)} beside the parts Zaram keeps loaded.`}
        {generated && ` List from ${generated}.`}
      </p>
    </div>
  );
}
