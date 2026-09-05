/**
 * Domains on the Knowledge surface.
 *
 * **No seventh node.** `CLAUDE.md` puts sources inside Knowledge and a domain
 * is how Knowledge organises them, so this is a section of that screen rather
 * than a place of its own.
 *
 * The description is a required field and is presented as one, because it is
 * load-bearing rather than decorative: routing reads it to decide when a domain
 * is worth reaching for, and a reply quotes it back — *"answered from your
 * Investing domain"*. The placeholder says what it is for instead of naming the
 * field, so the requirement reads as a reason rather than a rule.
 *
 * **A source is added to a domain, never moved into one.** The control is a set
 * of toggles, one per source, because many-to-many is the property that a tree
 * would destroy and a "move to…" verb would quietly imply. A contract is
 * Clients *and* Legal.
 */
import { useCallback, useState } from 'react';
import { Check, Layers, Loader2, Pencil, Plus, Trash2, X } from 'lucide-react';
import {
  addSourceToDomain,
  createDomain,
  deleteDomain,
  removeSourceFromDomain,
  renameDomain,
  type KnowledgeDomain,
} from '../../services/domainsClient';
import type { IngestSource } from '../../services/ingestClient';

interface DomainListProps {
  domains: KnowledgeDomain[];
  sources: IngestSource[];
  onChanged: () => void | Promise<void>;
}

export default function DomainList({ domains, sources, onChanged }: DomainListProps) {
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const reset = useCallback(() => {
    setCreating(false);
    setEditing(null);
    setName('');
    setDescription('');
    setError(null);
  }, []);

  const submit = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      if (editing) await renameDomain(editing, name, description);
      else await createDomain(name, description);
      reset();
      await onChanged();
    } catch (err) {
      // The backend's sentence, which names what to fix.
      setError(err instanceof Error ? err.message : 'Could not save that domain.');
    } finally {
      setBusy(false);
    }
  }, [editing, name, description, reset, onChanged]);

  const toggleSource = useCallback(
    async (domain: KnowledgeDomain, sourceId: string) => {
      const inDomain = domain.source_ids.includes(sourceId);
      try {
        if (inDomain) await removeSourceFromDomain(domain.id, sourceId);
        else await addSourceToDomain(domain.id, sourceId);
        await onChanged();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not change that.');
      }
    },
    [onChanged],
  );

  const remove = useCallback(
    async (domain: KnowledgeDomain) => {
      await deleteDomain(domain.id);
      if (expanded === domain.id) setExpanded(null);
      await onChanged();
    },
    [expanded, onChanged],
  );

  const form = (
    <div
      className="mt-2 rounded-xl px-5 py-4"
      style={{ border: '1px solid var(--color-border-subtle)', background: 'var(--color-glass)' }}
      data-testid="domain-form"
    >
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Name it — Investing, Clients, Coursework"
        data-testid="domain-name"
        className="w-full bg-transparent text-sm outline-none"
        style={{ color: 'var(--color-text)' }}
      />
      <input
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder="What's in it? Zaram uses this line to know when to read from it"
        data-testid="domain-description"
        className="mt-2 w-full bg-transparent text-xs outline-none"
        style={{ color: 'var(--color-text-muted)' }}
      />
      <div className="mt-3 flex items-center gap-2">
        <button
          onClick={submit}
          disabled={busy || !name.trim()}
          data-testid="domain-save"
          className="text-xs px-3 py-1.5 rounded-lg disabled:opacity-40 flex items-center gap-1.5"
          style={{ border: '1px solid var(--color-cyan-light)', color: 'var(--color-text)' }}
        >
          {busy && <Loader2 size={11} className="animate-spin" />}
          {editing ? 'Save' : 'Create'}
        </button>
        <button
          onClick={reset}
          className="text-xs px-3 py-1.5 rounded-lg"
          style={{ color: 'var(--color-text-dim, #64748b)' }}
        >
          Cancel
        </button>
      </div>
      {error && (
        <p className="mt-2 text-xs" style={{ color: 'var(--color-rose, #e11d48)' }} data-testid="domain-error">
          {error}
        </p>
      )}
    </div>
  );

  return (
    <div className="mt-6" data-testid="domains-section">
      <div className="flex items-center gap-2 mb-2">
        <h2 className="text-xs uppercase tracking-wide text-slate-500">
          Domains {domains.length > 0 && `· ${domains.length}`}
        </h2>
        <div className="flex-1" />
        {!creating && !editing && (
          <button
            onClick={() => { reset(); setCreating(true); }}
            data-testid="domain-new"
            className="text-[11px] px-2 py-1 rounded-md flex items-center gap-1"
            style={{ border: '1px solid var(--color-border-subtle)', color: 'var(--color-text)' }}
          >
            <Plus size={11} />
            New domain
          </button>
        )}
      </div>

      {domains.length === 0 && !creating && (
        <div
          className="rounded-xl px-6 py-8 text-center"
          style={{ border: '1px dashed var(--color-border-subtle)' }}
          data-testid="domains-empty"
        >
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>No domains yet.</p>
          <p className="mt-2 text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            A domain is a set of sources Zaram can answer from on purpose — your
            contracts, your coursework, the papers you're reading. Ask a question
            inside one and it reads only those, and says so.
          </p>
        </div>
      )}

      {(creating || editing) && form}

      {domains.length > 0 && (
        <div className="space-y-2" data-testid="domains-list">
          {domains.map((domain) => (
            <div
              key={domain.id}
              className="rounded-xl px-5 py-3"
              style={{ border: '1px solid var(--color-border-subtle)' }}
              data-testid={`domain-${domain.id}`}
            >
              <div className="flex items-center gap-3">
                <Layers size={15} style={{ color: 'var(--color-indigo-light)' }} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate" style={{ color: 'var(--color-text)' }}>
                    {domain.name}
                  </p>
                  {/* The line routing reads. Shown because the user needs to
                      see what Zaram will act on. */}
                  <p className="text-[11px] text-slate-500 truncate">{domain.description}</p>
                </div>

                <button
                  onClick={() => setExpanded(expanded === domain.id ? null : domain.id)}
                  className="text-[11px] px-2 py-1 rounded-md shrink-0"
                  style={{ border: '1px solid var(--color-border-subtle)', color: 'var(--color-text)' }}
                  data-testid={`domain-sources-${domain.id}`}
                >
                  {domain.source_ids.length} {domain.source_ids.length === 1 ? 'source' : 'sources'}
                </button>

                <button
                  onClick={() => {
                    setCreating(false);
                    setEditing(domain.id);
                    setName(domain.name);
                    setDescription(domain.description);
                  }}
                  title="Rename this domain"
                  className="shrink-0 opacity-60 hover:opacity-100"
                  data-testid={`domain-edit-${domain.id}`}
                >
                  <Pencil size={12} style={{ color: 'var(--color-text-dim, #64748b)' }} />
                </button>

                <button
                  onClick={() => void remove(domain)}
                  // Says what it does *not* do, because the button beside it on
                  // this screen — withdrawing a source — does delete documents.
                  title="Remove this domain. Your sources and everything Zaram learned from them stay."
                  className="shrink-0 opacity-60 hover:opacity-100"
                  data-testid={`domain-remove-${domain.id}`}
                >
                  <Trash2 size={12} style={{ color: 'var(--color-text-dim, #64748b)' }} />
                </button>
              </div>

              {expanded === domain.id && (
                <div className="mt-3 pt-3 space-y-1" style={{ borderTop: '1px solid var(--color-border-subtle)' }}>
                  {sources.length === 0 ? (
                    <p className="text-xs text-slate-500">
                      Nothing to add yet — drop some documents above first.
                    </p>
                  ) : (
                    sources.map((source) => {
                      const inDomain = domain.source_ids.includes(source.id);
                      return (
                        <button
                          key={source.id}
                          onClick={() => void toggleSource(domain, source.id)}
                          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left"
                          style={{ background: inDomain ? 'var(--color-glass)' : 'transparent' }}
                          data-testid={`domain-toggle-${domain.id}-${source.id}`}
                        >
                          {inDomain ? (
                            <Check size={12} style={{ color: 'var(--color-emerald)' }} />
                          ) : (
                            <X size={12} style={{ color: 'var(--color-text-faint, #3a3f5c)' }} />
                          )}
                          <span className="text-xs truncate flex-1" style={{ color: 'var(--color-text)' }}>
                            {source.name}
                          </span>
                          <span className="text-[11px] text-slate-500 shrink-0">
                            {source.counts.indexed ?? 0} indexed
                          </span>
                        </button>
                      );
                    })
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
