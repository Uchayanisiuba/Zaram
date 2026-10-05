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
import { Check, Copy, Download, Loader2, Search } from 'lucide-react';

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

/** What each capability means to someone who has never heard the word. The
 *  badge carries the short form; the drawer carries the sentence. */
const CAPABILITY_WORDS: Record<string, { badge: string; means: string }> = {
  vision: { badge: 'reads images', means: 'Can look at a picture or a screenshot you give it, not only text.' },
  tools: { badge: 'uses tools', means: 'Can call the tools you attach — search a folder, make a document — rather than only talk about them.' },
  thinking: { badge: 'thinks first', means: 'Works through a problem before answering. Slower to start, better on anything with steps.' },
};

/** The part of a tag after the colon, which is where a build says how it was
 *  squeezed. Said plainly where the manifest's own tags make it knowable, and
 *  not guessed for a tag that does not. */
function buildNote(name: string): string {
  const tag = name.split(':')[1] ?? '';
  if (/qat/i.test(tag)) return 'Trained at the size it ships in, so it loses less than an ordinary 4-bit build.';
  if (/^\d+(\.\d+)?b$/i.test(tag)) return 'The size in billions of parameters; the default build for this size.';
  return 'The default build.';
}

export default function ModelBrowser({ onInstalled }: Props) {
  const [models, setModels] = useState<CatalogueModel[]>([]);
  const [budget, setBudget] = useState<number | null>(null);
  const [generated, setGenerated] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState('');
  const [pulling, setPulling] = useState<Pulling>(null);
  const [failure, setFailure] = useState('');
  const [reached, setReached] = useState(true);
  const [openDetails, setOpenDetails] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  async function copy(name: string, text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(name);
      window.setTimeout(() => setCopied((was) => (was === name ? null : was)), 2000);
    } catch {
      // No clipboard (a locked-down webview): the command is on screen and
      // selectable, which is the fallback. Not an error worth a banner.
    }
  }

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
    <div className="flex h-full min-h-0 flex-col" data-testid="model-browser">
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
                    {model.runtime === 'tabby' && ' · TabbyAPI'}
                  </p>
                  {(model.capabilities?.length ?? 0) > 0 && (
                    <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="What it can do">
                      {model.capabilities!.map((c) => (
                        <li
                          key={c}
                          data-testid={`capability-${model.name}-${c}`}
                          className="rounded-full px-2 py-0.5 text-[11px]"
                          style={{
                            border: '1px solid var(--color-border)',
                            color: 'var(--color-text-muted)',
                          }}
                        >
                          {CAPABILITY_WORDS[c]?.badge ?? c}
                        </li>
                      ))}
                    </ul>
                  )}
                  <button
                    type="button"
                    data-testid={`details-${model.name}`}
                    aria-expanded={openDetails === model.name}
                    onClick={() => setOpenDetails((was) => (was === model.name ? null : model.name))}
                    className="mt-2 text-xs underline-offset-2 hover:underline"
                    style={{ color: 'var(--color-cyan-light)' }}
                  >
                    {openDetails === model.name ? 'Hide details' : 'Details'}
                  </button>
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
                  ) : model.runtime === 'tabby' ? (
                    // Not a download button. Zaram cannot fetch an EXL3 build --
                    // TabbyAPI keeps its models where its own config says -- so
                    // the row says whose job it is, and Details has the command.
                    <span
                      data-testid={`via-tabby-${model.name}`}
                      className="text-xs"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      you fetch this one — see Details
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

              {openDetails === model.name && (
                <dl
                  data-testid={`details-panel-${model.name}`}
                  className="mt-3 space-y-2 rounded-lg px-3 py-2 text-xs"
                  style={{ background: 'var(--color-glass)', color: 'var(--color-text-muted)' }}
                >
                  <div>
                    <dt className="mb-0.5 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)', fontSize: 10 }}>Download</dt>
                    <dd style={{ color: 'var(--color-text)' }}>
                      About {gigabytes(model.size_bytes)}, once. Approximate: the download reports the
                      real total as it goes.
                    </dd>
                  </div>
                  <div>
                    <dt className="mb-0.5 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)', fontSize: 10 }}>This machine</dt>
                    <dd style={{ color: 'var(--color-text)' }}>
                      {model.fits === null
                        ? 'Zaram could not measure this machine’s graphics memory, so it cannot say.'
                        : model.fits
                          ? 'Fits, with room left beside the parts Zaram keeps loaded.'
                          : 'Needs more memory than this machine has.'}
                    </dd>
                  </div>
                  <div>
                    <dt className="mb-0.5 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)', fontSize: 10 }}>What it can do</dt>
                    <dd style={{ color: 'var(--color-text)' }}>
                      {(model.capabilities?.length ?? 0) > 0 ? (
                        <ul className="space-y-1">
                          {model.capabilities!.map((c) => (
                            <li key={c}>
                              <strong style={{ color: 'var(--color-text)' }}>
                                {CAPABILITY_WORDS[c]?.badge ?? c}.
                              </strong>{' '}
                              {CAPABILITY_WORDS[c]?.means}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        'Zaram’s list does not say. That is not the same as it being unable.'
                      )}
                    </dd>
                  </div>
                  {model.install_command && (
                    <div>
                      <dt className="mb-0.5 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)', fontSize: 10 }}>How to get it</dt>
                      <dd style={{ color: 'var(--color-text)' }}>
                        Zaram does not download this one: TabbyAPI loads from a folder set in its own
                        config, which Zaram cannot read. Run this, with that folder in place of the
                        placeholder, then restart or reload TabbyAPI.
                        <div
                          className="mt-1.5 flex items-start gap-2 rounded px-2 py-1.5"
                          style={{ background: 'rgba(0,0,0,0.3)', fontFamily: 'var(--font-mono)' }}
                        >
                          <code data-testid={`command-${model.name}`} className="min-w-0 flex-1 break-all select-all">
                            {model.install_command}
                          </code>
                          <button
                            type="button"
                            data-testid={`copy-${model.name}`}
                            aria-label="Copy the command"
                            onClick={() => void copy(model.name, model.install_command!)}
                            className="shrink-0 rounded p-1"
                            style={{ color: 'var(--color-text-muted)' }}
                          >
                            {copied === model.name ? <Check size={13} aria-hidden /> : <Copy size={13} aria-hidden />}
                          </button>
                        </div>
                      </dd>
                    </div>
                  )}
                  <div>
                    <dt className="mb-0.5 uppercase tracking-wide" style={{ color: 'var(--color-text-muted)', fontSize: 10 }}>This build</dt>
                    <dd style={{ color: 'var(--color-text)' }}>{buildNote(model.name)}</dd>
                  </div>
                </dl>
              )}

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
        {/* Said once, where it is read: why Details holds a sentence and not a
            model page. Fetching one would be a network call nobody asked for. */}
        {' '}Details are the list’s own description — Zaram does not fetch a model’s page to fill them.
      </p>
    </div>
  );
}
