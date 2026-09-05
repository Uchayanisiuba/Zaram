/**
 * How a reply's artifacts are laid out: some as cards, a run of pictures as
 * one grid.
 *
 * A pure function with its own tests, rather than a `reduce` inside the render
 * — the interesting behaviour is the *grouping rule*, and a rule embedded in
 * JSX is one nobody can assert on.
 *
 * The rule: **consecutive pictures from one reply are one group.**
 *
 * Consecutive rather than "all of them", because order is the only thing
 * carrying the relationship. Four images from one request arrive together, in
 * a run; an image, then a document, then another image is three separate
 * results that happen to share a reply, and folding the two pictures together
 * would claim a relationship the exchange never had. Grouping by kind alone
 * would do exactly that.
 */
import { PICTORIAL_KINDS, type Artifact } from '@/services/artifactsClient';

export type ArtifactGroup =
  /** One artifact, drawn as an `ArtifactCard`. */
  | { kind: 'single'; artifact: Artifact }
  /** A run of pictures, drawn as one `ArtifactGrid`. */
  | { kind: 'gallery'; artifacts: Artifact[] };

export function groupArtifacts(artifacts: readonly Artifact[]): ArtifactGroup[] {
  const groups: ArtifactGroup[] = [];

  for (const artifact of artifacts) {
    if (!PICTORIAL_KINDS.has(artifact.kind)) {
      groups.push({ kind: 'single', artifact });
      continue;
    }

    const last = groups[groups.length - 1];
    if (last && last.kind === 'gallery') {
      last.artifacts.push(artifact);
    } else {
      groups.push({ kind: 'gallery', artifacts: [artifact] });
    }
  }

  return groups;
}
