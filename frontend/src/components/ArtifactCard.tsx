/**
 * The file card — a document Zaram made, shown where it was made.
 *
 * CLAUDE.md: generated files appear as cards in the conversation and land in
 * the output directory. There is no Files surface, because that duplicates the
 * operating system.
 *
 * This draws the same record Work draws a row from. One shape, two renderings —
 * if a card and a row could disagree about what exists, one of them is lying,
 * and the user has no way to tell which.
 *
 * Deliberately quiet. A generated file is a result, not an event: it sits in
 * the transcript at the point it was made and does not animate, expand or
 * demand acknowledgement. Motion has a budget and this is not worth any of it.
 */
import { useEffect, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import {
  BarChart3,
  Download,
  Eye,
  FileSpreadsheet,
  FileText,
  ImageIcon,
  Presentation,
  Quote,
  Receipt,
  UserRound,
} from 'lucide-react';

import ArtifactPreview from '@/components/ArtifactPreview';
import { useArtifactImage } from '@/hooks/useArtifactImage';
import {
  downloadArtifact,
  PICTORIAL_KINDS,
  type Artifact,
  type ArtifactKind,
} from '@/services/artifactsClient';

const KIND_ICON: Record<ArtifactKind, React.ReactNode> = {
  invoice: <Receipt size={15} />,
  document: <FileText size={15} />,
  spreadsheet: <FileSpreadsheet size={15} />,
  chart: <BarChart3 size={15} />,
  deck: <Presentation size={15} />,
  cv: <UserRound size={15} />,
  image: <ImageIcon size={15} />,
};

const KIND_COLOUR: Record<ArtifactKind, string> = {
  invoice: 'var(--color-emerald)',
  document: 'var(--color-cyan-light)',
  spreadsheet: 'var(--color-amber)',
  chart: 'var(--color-violet)',
  deck: 'var(--color-indigo-light)',
  cv: 'var(--color-cyan-light)',
  image: 'var(--color-indigo-light)',
};

const bytes = (n: number) => {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} kB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
};

export default function ArtifactCard({
  artifact,
  onOpenInWork,
}: {
  artifact: Artifact;
  onOpenInWork?: (id: string) => void;
}) {
  const extension = artifact.filename.split('.').pop()?.toUpperCase() ?? 'FILE';
  const citedCount = artifact.claims?.length ?? 0;
  const [previewing, setPreviewing] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const pictorial = PICTORIAL_KINDS.has(artifact.kind);
  const thumbnail = useArtifactImage(artifact.id, pictorial && artifact.exists);

  // **Opens itself only when the artifact was the point of the request.**
  //
  // Ask for an image and the panel comes forward the moment it is ready; an
  // artifact that turned up alongside a reply does not seize the screen, and
  // that is the whole distinction `deliberate` carries. An overlay arriving
  // unbidden mid-conversation is an interruption, not a convenience.
  //
  // Once, and only for a file that is actually there. Keyed on the id so a
  // second image in the same conversation opens on its own account rather
  // than being suppressed by the first, and guarded on `exists` so the panel
  // never comes forward over a file the write did not produce.
  const [autoOpened, setAutoOpened] = useState('');
  useEffect(() => {
    if (!artifact.deliberate || !artifact.exists) return;
    if (autoOpened === artifact.id) return;
    setAutoOpened(artifact.id);
    setPreviewing(true);
  }, [artifact.deliberate, artifact.exists, artifact.id, autoOpened]);

  return (
    <div
      className="my-2 rounded-xl overflow-hidden"
      style={{
        border: '1px solid var(--color-border-subtle)',
        background: 'var(--color-glass)',
        maxWidth: 520,
      }}
    >
      {/* The picture, on the card, for a kind whose file *is* one.
          A filename is a poor description of an image — you cannot tell
          whether it is the one you wanted without opening it — and Work's job
          and this card's job are both to save that opening. Above the row
          rather than beside it, so the image gets the card's full width. */}
      {pictorial && thumbnail.url && (
        <button
          type="button"
          onClick={() => setPreviewing(true)}
          className="block w-full"
          style={{ lineHeight: 0, background: 'var(--color-surface-sunken, #0b1120)' }}
          aria-label={`Preview ${artifact.filename}`}
        >
          <img
            src={thumbnail.url}
            alt={artifact.filename}
            className="w-full"
            style={{ maxHeight: 320, objectFit: 'contain' }}
          />
        </button>
      )}

      <div className="flex items-start gap-3 px-4 py-3">
        <span className="mt-0.5 shrink-0" style={{ color: KIND_COLOUR[artifact.kind] }}>
          {KIND_ICON[artifact.kind]}
        </span>

        <div className="flex-1 min-w-0">
          <div className="text-sm break-all" style={{ color: 'var(--color-text)' }}>
            {artifact.filename}
          </div>
          <div
            className="mt-0.5 text-[11px]"
            style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}
          >
            {extension} · {bytes(artifact.size_bytes)}
            {/* Where it went. A file the user cannot find is a file they did
                not receive, and "check your output folder" is not an answer if
                nobody said which folder. */}
            {artifact.path && (
              <>
                {' · '}
                <span title={artifact.path}>saved to your output folder</span>
              </>
            )}
          </div>
        </div>
      </div>

      {citedCount > 0 && (
        <div
          className="px-4 pb-3 space-y-1.5"
          style={{ borderTop: '1px solid var(--color-border-subtle)', paddingTop: 10 }}
        >
          {/* Provenance on the card, not only in the file. The claim is the
              reason this document is defensible, and burying it inside a
              .docx the user has not opened yet means they never see it. */}
          <div
            className="text-[10px] uppercase tracking-wider"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {citedCount === 1 ? '1 claim traced' : `${citedCount} claims traced`}
          </div>
          {artifact.claims.slice(0, 2).map((claim) => (
            <div
              key={claim.id}
              className="flex items-start gap-2 text-[11px]"
              style={{ color: 'var(--color-text-muted-light)' }}
            >
              <Quote
                size={10}
                className="mt-0.5 shrink-0"
                style={{ color: 'var(--color-cyan-light)' }}
              />
              <span className="min-w-0">
                <span className="block truncate">{claim.excerpt}</span>
                <span
                  className="block truncate"
                  style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}
                >
                  {claim.source_id}
                </span>
              </span>
            </div>
          ))}
          {citedCount > 2 && (
            <div
              className="text-[11px]"
              style={{ color: 'var(--color-text-faint)' }}
            >
              and {citedCount - 2} more
            </div>
          )}
        </div>
      )}

      <div
        className="flex items-center gap-2 px-4 py-2.5"
        style={{ borderTop: '1px solid var(--color-border-subtle)' }}
      >
        {/* Never a download button over a file that is not there. `exists` is
            the backend having stat'd the path, not an assumption that writing
            succeeded. */}
        {artifact.exists ? (
          <>
            {/* Preview sits beside Download, not instead of it. The preview is
                the HTML the file was built from — `CLAUDE.md` makes HTML the
                source of truth for every generated document precisely so this
                cannot drift from what downloads. */}
            <button
              type="button"
              onClick={() => setPreviewing(true)}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] transition-colors hover:bg-white/5"
              style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            >
              <Eye size={12} />
              Preview
            </button>
            {/* A button, not a link, and that is not a style choice.
                `RequireApiSecret` authenticates every request and the
                credential is attached by a wrapper around `fetch` — an anchor
                navigates without it and gets 401. See `downloadUrl`. */}
            <button
              type="button"
              onClick={() => {
                setDownloadError(null);
                downloadArtifact(artifact.id, artifact.filename).catch((err: unknown) =>
                  setDownloadError(
                    err instanceof Error ? err.message : 'Could not download that file.',
                  ),
                );
              }}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] transition-colors hover:bg-white/5"
              style={{ border: '1px solid var(--color-border)', color: 'var(--color-text)' }}
            >
              <Download size={12} />
              Download
            </button>
          </>
        ) : (
          <span
            className="text-[11px]"
            style={{ color: 'var(--color-text-faint)' }}
            title="The record is here but the file is not at the path it was written to"
          >
            File not found where it was written
          </span>
        )}

        {onOpenInWork && (
          <button
            onClick={() => onOpenInWork(artifact.id)}
            className="rounded-lg px-2.5 py-1 text-[11px] transition-colors hover:bg-white/5"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Show in Work
          </button>
        )}
      </div>

      {/* A download that failed has to say so. Silently doing nothing is what
          the anchor did for a week, and it is indistinguishable from a click
          that missed. */}
      {downloadError && (
        <div
          className="px-4 pb-2.5 text-[11px]"
          style={{ color: '#fca5a5' }}
          role="alert"
        >
          {downloadError}
        </div>
      )}

      <AnimatePresence>
        {previewing && (
          <ArtifactPreview artifact={artifact} onClose={() => setPreviewing(false)} />
        )}
      </AnimatePresence>
    </div>
  );
}
