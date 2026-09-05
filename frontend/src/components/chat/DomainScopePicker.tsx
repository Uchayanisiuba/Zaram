/**
 * Which knowledge domain a question is asked inside.
 *
 * The domain machinery landed with no way to use it from a question: the scope
 * was proven at the retriever and nothing in the chat path ever passed
 * `only_ids`. Configurable, not usable. This is the control that closes that.
 *
 * **Beside the input, next to the project, not a surface.** A domain is a
 * property of the question you are about to ask, so it belongs where you ask
 * it — and it sits where the consequence is, since the user can see what Zaram
 * is allowed to read at the moment they write.
 *
 * **One at a time, deliberately, and it is not a one-way door.** The backend
 * unions several — asking across *Clients* and *Legal* means either — and both
 * `fact_ids_for` and `describe` handle any number. The wire format is already a
 * list. But a multi-select beside a text input is a control nobody operates
 * casually, and narrowing to one library is the case that actually comes up;
 * offering the harder control first would be making the user choose in advance
 * (rule 7h). Adding multiple selection later changes this component and nothing
 * behind it.
 *
 * Names, not ids, unlike `ProjectScopePicker` — a domain *has* a name the user
 * typed, and its description is required precisely so it can be read back.
 */
import { useEffect, useState } from 'react';
import { Library } from 'lucide-react';

import { useChatStore } from '@/stores/chatStore';
import { fetchDomains, type KnowledgeDomain } from '@/services/domainsClient';

export default function DomainScopePicker() {
  const domainIds = useChatStore((s) => s.domainIds);
  const setDomains = useChatStore((s) => s.setDomains);

  const [domains, setDomains_] = useState<KnowledgeDomain[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const found = await fetchDomains();
        if (!cancelled) setDomains_(found);
      } catch {
        // A list we could not fetch is not an empty list. Saying so beats
        // offering "All knowledge" as though it were the only option — the
        // user would believe no domains exist and never look for the control.
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Nothing to narrow to. Rendering an empty picker would advertise a feature
  // the user has not set up and cannot act on from here.
  if (!failed && domains.length === 0) return null;

  const selected = domainIds[0] ?? '';
  // The stored domain may have been deleted since it was chosen. Keeping it as
  // an option means the narrowing never silently widens to the whole Spine
  // without the user seeing that it changed.
  const missing = selected && !domains.some((d) => d.id === selected);

  return (
    <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
      <Library size={12} aria-hidden className="shrink-0" />
      <label htmlFor="domain-scope" className="sr-only">
        Knowledge domain this question is asked inside
      </label>
      <select
        id="domain-scope"
        value={selected}
        onChange={(e) => setDomains(e.target.value ? [e.target.value] : [])}
        className="bg-transparent text-[11px] text-slate-400 outline-none cursor-pointer hover:text-slate-300 focus:text-slate-200 transition-colors"
      >
        {/* Not "No domain". Choosing nothing means Zaram may read everything,
            which is the opposite claim from an empty domain — and those two
            are exactly the states the backend keeps apart with `None` against
            an empty set. */}
        <option value="">All knowledge</option>
        {missing && (
          <option value={selected}>{selected} (no longer exists)</option>
        )}
        {domains.map((d) => (
          <option key={d.id} value={d.id} title={d.description}>
            {d.name}
          </option>
        ))}
      </select>
      {failed && (
        <span className="text-slate-600" title="Could not reach the backend">
          · list unavailable
        </span>
      )}
    </div>
  );
}
