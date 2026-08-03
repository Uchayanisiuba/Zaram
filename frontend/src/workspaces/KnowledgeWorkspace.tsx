/**
 * Sources — where Zaram's knowledge comes from.
 *
 * This screen previously listed fabricated academic papers ("Vaswani et al.,
 * 2017") with invented relevance scores and related-document strengths. None of
 * it existed; nothing had ever been ingested.
 *
 * Folder ingest is in the v1 scope but is not built, so there is nothing real
 * to list. Rather than invent something, the screen says what is true and what
 * will change when it is built.
 *
 * `docs/UI-SPEC.md` calls this screen Sources and gives it a drag-and-drop
 * target, indexing progress and a per-folder scope toggle. That is the shape to
 * build here once ingest exists.
 */
import { FolderOpen, ShieldCheck } from 'lucide-react';

export default function KnowledgeWorkspace() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="px-8 pt-6 pb-4 flex items-center gap-3">
        <FolderOpen size={20} style={{ color: 'var(--color-cyan-light)' }} />
        <h1
          className="text-lg font-semibold"
          style={{ fontFamily: 'var(--font-display)', color: 'var(--color-text)' }}
        >
          Sources
        </h1>
      </div>

      <div className="flex-1 overflow-y-auto px-8 pb-8">
        <div
          className="rounded-xl px-6 py-10 text-center"
          style={{
            border: '1px dashed var(--color-border-subtle)',
            background: 'var(--color-glass)',
          }}
        >
          <p className="text-sm" style={{ color: 'var(--color-text)' }}>
            No sources yet.
          </p>
          <p className="mt-2 text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            Pointing Zaram at a folder is not built yet. When it is, the files
            you choose will be indexed into the Spine and every answer drawn
            from them will cite the document and passage it came from.
          </p>
          <p className="mt-4 text-xs text-slate-500">
            Until then, Zaram only knows what you tell it in conversation. You
            can see all of it under <span style={{ color: 'var(--color-text)' }}>Memory</span>.
          </p>
        </div>

        <div
          className="mt-4 rounded-xl px-5 py-4 flex items-start gap-3"
          style={{ border: '1px solid var(--color-border-subtle)' }}
        >
          <ShieldCheck size={16} className="mt-0.5 shrink-0" style={{ color: 'var(--color-emerald)' }} />
          <div>
            <p className="text-xs" style={{ color: 'var(--color-text)' }}>
              Each source will carry its own privacy setting
            </p>
            <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
              A folder can be marked local-only, so nothing drawn from it is
              ever sent to a cloud model. That control ships with ingest, not
              after it.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
