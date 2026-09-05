/**
 * Several pictures from one request, as one card.
 *
 * Why one card and not four
 * -------------------------
 * A request for four images produced four `ArtifactCard`s, which floods the
 * conversation with what is really one answer — and three of the four are
 * about to be passed over. The wait was one wait and the result is one result,
 * so it gets one card, and the user picks from a 2x2 grid.
 *
 * What "pick" means here, and what it does not
 * --------------------------------------------
 * Picking opens that image and offers it for download. It does **not** delete
 * the other three, and that is structural rather than an omission:
 * `ArtifactStore` has no capability to delete or overwrite anything, by
 * design, and CLAUDE.md is explicit that removing a *file* is the operating
 * system's job. All four stay in the output folder and all four appear in
 * Work. So the card says "keep" in the sense of "this is the one I wanted",
 * never in the sense of "throw the rest away" — offering a button that
 * appeared to discard files and did not would be worse than offering none.
 *
 * Only for pictures
 * -----------------
 * Grouping is by kind, not by count. Four documents are four different things
 * a user reads one at a time and needs the filenames of; four images are four
 * attempts at one thing, compared at a glance. The grid is the density that
 * suits the second and not the first.
 */
import { useEffect, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { Check, Download, ImageIcon, Save } from 'lucide-react';

import ArtifactPreview from '@/components/ArtifactPreview';
import { useArtifactImage } from '@/hooks/useArtifactImage';
import {
  downloadArtifact,
  keepArtifact,
  type Artifact,
} from '@/services/artifactsClient';
import { clearsLabel } from '@/lib/staging';

function Tile({
  artifact,
  onOpen,
}: {
  artifact: Artifact;
  onOpen: () => void;
}) {
  const image = useArtifactImage(artifact.id, artifact.exists);
  // What the server last said about this file, once Save has changed it.
  // Local rather than lifted, because keeping one tile says nothing about
  // the other three and a shared piece of state would have to explain that.
  const [kept, setKept] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const staged = artifact.staged && !kept;

  // A div wrapping the button, not a button wrapping buttons. Save and
  // Download are actions on this image and the tile itself opens it, and
  // nesting the three would be invalid HTML that browsers repair by moving
  // elements out of it — which is how a click target ends up somewhere
  // nobody put it.
  return (
    <div className="relative" style={{ aspectRatio: '1 / 1' }}>
    <button
      type="button"
      onClick={onOpen}
      className="relative h-full w-full overflow-hidden rounded-lg transition-opacity hover:opacity-90"
      style={{
        background: 'var(--color-surface-sunken, #0b1120)',
        border: '1px solid var(--color-border-subtle)',
      }}
      aria-label={`Open ${artifact.filename}`}
    >
      {image.url ? (
        <img
          src={image.url}
          alt={artifact.filename}
          className="h-full w-full"
          style={{ objectFit: 'cover' }}
        />
      ) : (
        <span
          className="flex h-full w-full items-center justify-center"
          style={{ color: 'var(--color-text-faint)' }}
          title={image.error ?? undefined}
        >
          <ImageIcon size={18} />
        </span>
      )}
    </button>

      {/* Over the image rather than under it, so four tiles stay square and
          the row does not grow a second height. Always visible, never on
          hover: a control the user has to discover by waving at it is a
          control most people never find, and this one is the difference
          between keeping the picture and losing it. */}
      {artifact.exists && (
        <div className="absolute inset-x-1 bottom-1 flex items-center justify-end gap-1">
          {staged && (
            <button
              type="button"
              disabled={saving}
              onClick={() => {
                setSaveError(null);
                setSaving(true);
                keepArtifact(artifact.id)
                  .then(() => setKept(true))
                  .catch((err: unknown) =>
                    setSaveError(
                      err instanceof Error ? err.message : 'Could not save that file.',
                    ),
                  )
                  .finally(() => setSaving(false));
              }}
              className="flex items-center gap-1 rounded-md px-1.5 py-1 text-[10px] backdrop-blur transition-colors hover:bg-black/70"
              style={{ background: 'rgba(2,6,23,0.55)', color: '#e2e8f0' }}
              title="Save this one to your output folder"
            >
              <Save size={11} />
              Save
            </button>
          )}
          {kept && (
            <span
              className="flex items-center gap-1 rounded-md px-1.5 py-1 text-[10px] backdrop-blur"
              style={{ background: 'rgba(2,6,23,0.55)', color: '#86efac' }}
              title="In your output folder"
            >
              <Check size={11} />
              Saved
            </span>
          )}
          <button
            type="button"
            onClick={() => {
              setSaveError(null);
              downloadArtifact(artifact.id, artifact.filename).catch((err: unknown) =>
                setSaveError(
                  err instanceof Error ? err.message : 'Could not download that file.',
                ),
              );
            }}
            className="flex items-center gap-1 rounded-md px-1.5 py-1 text-[10px] backdrop-blur transition-colors hover:bg-black/70"
            style={{ background: 'rgba(2,6,23,0.55)', color: '#e2e8f0' }}
            title={`Download ${artifact.filename}`}
            aria-label={`Download ${artifact.filename}`}
          >
            <Download size={11} />
          </button>
        </div>
      )}

      {/* A failure has to say so. Silently doing nothing is indistinguishable
          from a click that missed. */}
      {saveError && (
        <div
          className="absolute inset-x-1 top-1 rounded-md px-1.5 py-1 text-[10px]"
          style={{ background: 'rgba(2,6,23,0.75)', color: '#fca5a5' }}
        >
          {saveError}
        </div>
      )}
    </div>
  );
}

export default function ArtifactGrid({ artifacts }: { artifacts: Artifact[] }) {
  const [opened, setOpened] = useState<Artifact | null>(null);
  // The first one still waiting, which is what the footer counts down. They
  // were written seconds apart, so any of them gives the same answer to the
  // nearest hour — and picking the first keeps the line steady as tiles are
  // saved one by one rather than jumping to a new deadline each time.
  const waiting = artifacts.find((a) => a.staged && a.expires_at);

  // **Opens itself only when the pictures were the point of the request.**
  // Same rule as the single card: the first of a deliberate batch comes
  // forward once it is ready, and a batch that turned up alongside a reply
  // does not seize the screen.
  const [autoOpened, setAutoOpened] = useState('');
  const first: Artifact | undefined = artifacts[0];
  useEffect(() => {
    if (!first?.deliberate || !first.exists) return;
    if (autoOpened === first.id) return;
    setAutoOpened(first.id);
    setOpened(first);
  }, [first, autoOpened]);

  if (artifacts.length === 0) return null;

  return (
    <div
      className="my-2 rounded-xl overflow-hidden"
      style={{
        border: '1px solid var(--color-border-subtle)',
        background: 'var(--color-glass)',
        maxWidth: 520,
      }}
    >
      <div
        className="grid gap-2 p-2"
        style={{
          // Two columns for a batch, one when there happens to be a pair —
          // a 2x1 of tall cells reads better than two half-width ones.
          gridTemplateColumns: artifacts.length > 1 ? '1fr 1fr' : '1fr',
        }}
      >
        {artifacts.map((artifact) => (
          <Tile key={artifact.id} artifact={artifact} onOpen={() => setOpened(artifact)} />
        ))}
      </div>

      <div
        className="flex items-center gap-2 px-4 py-2.5"
        style={{ borderTop: '1px solid var(--color-border-subtle)' }}
      >
        <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
          {artifacts.length === 1
            ? '1 image'
            : `${artifacts.length} images · pick one to open it`}
        </span>
        <div className="flex-1" />
        {/* **What is actually true of these files, which is not that they
            were saved.** This line used to read "saved to your output
            folder" for every image, and the maintainer asked the obvious
            question: should the user not choose what to save? They should —
            a request for a picture produces several and most are discards.
            So the images wait, this says how long for, and the Save button
            on each tile is the way out. See `artifacts/staging.py`.

            The window is stated, never implied. A retention window the user
            cannot see is indistinguishable from a product that loses
            files. */}
        <span
          className="text-[11px]"
          style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}
          title={artifacts[0].path ?? undefined}
        >
          {waiting?.expires_at
            ? clearsLabel(waiting.expires_at)
            : 'saved to your output folder'}
        </span>
      </div>

      <AnimatePresence>
        {opened && (
          <ArtifactPreview artifact={opened} onClose={() => setOpened(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}
