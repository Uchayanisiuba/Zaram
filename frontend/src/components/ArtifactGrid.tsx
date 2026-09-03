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
import { ImageIcon } from 'lucide-react';

import ArtifactPreview from '@/components/ArtifactPreview';
import { useArtifactImage } from '@/hooks/useArtifactImage';
import { type Artifact } from '@/services/artifactsClient';

function Tile({
  artifact,
  onOpen,
}: {
  artifact: Artifact;
  onOpen: () => void;
}) {
  const image = useArtifactImage(artifact.id, artifact.exists);

  return (
    <button
      type="button"
      onClick={onOpen}
      className="relative overflow-hidden rounded-lg transition-opacity hover:opacity-90"
      style={{
        // Square cells, so four images of the same size tile without one of
        // them setting the row height for the others.
        aspectRatio: '1 / 1',
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
  );
}

export default function ArtifactGrid({ artifacts }: { artifacts: Artifact[] }) {
  const [opened, setOpened] = useState<Artifact | null>(null);

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
        <span
          className="text-[11px]"
          style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-faint)' }}
          title={artifacts[0].path ?? undefined}
        >
          saved to your output folder
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
