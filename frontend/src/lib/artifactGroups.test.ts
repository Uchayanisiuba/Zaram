/**
 * The rule that turns four cards into one.
 *
 * Worth its own file because the rule is the interesting part and it has an
 * edge nobody would guess from the description: grouping is by *consecutive
 * run*, not by kind. Asserting that here is what stops a later simplification
 * to `artifacts.filter(isPicture)` — which reads better, passes an eyeball
 * check, and quietly claims a relationship between two images that arrived
 * either side of a document.
 */
import { describe, expect, it } from 'vitest';

import { groupArtifacts } from './artifactGroups';
import type { Artifact, ArtifactKind } from '@/services/artifactsClient';

function artifact(id: string, kind: ArtifactKind): Artifact {
  return {
    id,
    filename: `${id}.${kind === 'image' || kind === 'chart' ? 'png' : 'docx'}`,
    kind,
    project_id: '',
    origin: 'generated',
    created_at: 0,
    size_bytes: 1,
    path: `/out/${id}`,
    conversation_id: '',
    conversation_title: '',
    sources: [],
    claims: [],
    indexed: true,
    remember_override: null,
    exists: true,
  };
}

describe('groupArtifacts', () => {
  it('leaves a reply with no artifacts alone', () => {
    expect(groupArtifacts([])).toEqual([]);
  });

  it('draws a lone document as a card', () => {
    const groups = groupArtifacts([artifact('a', 'document')]);
    expect(groups).toHaveLength(1);
    expect(groups[0].kind).toBe('single');
  });

  it('collapses a batch of images into one gallery', () => {
    const groups = groupArtifacts([
      artifact('a', 'image'),
      artifact('b', 'image'),
      artifact('c', 'image'),
      artifact('d', 'image'),
    ]);

    expect(groups).toHaveLength(1);
    expect(groups[0].kind).toBe('gallery');
    if (groups[0].kind === 'gallery') {
      expect(groups[0].artifacts.map((a) => a.id)).toEqual(['a', 'b', 'c', 'd']);
    }
  });

  it('keeps a single image as a gallery of one', () => {
    // Rather than as a card, so one image and four images are drawn by the
    // same component. Two components for one kind is two places for the
    // download, the preview and the auto-open rule to disagree.
    const groups = groupArtifacts([artifact('a', 'image')]);
    expect(groups[0].kind).toBe('gallery');
  });

  it('does not join pictures that were separated by something else', () => {
    // The edge the rule exists for. Two images either side of a document are
    // two results that happen to share a reply, not a batch — and drawing
    // them as one grid would assert a relationship the exchange never had.
    const groups = groupArtifacts([
      artifact('a', 'image'),
      artifact('b', 'document'),
      artifact('c', 'image'),
    ]);

    expect(groups.map((g) => g.kind)).toEqual(['gallery', 'single', 'gallery']);
  });

  it('groups charts with images, because both are pictures', () => {
    // They stay two *kinds* — a chart carries the data table that makes it
    // checkable and an image has nothing behind it to check — but for the
    // question this function answers, "is a thumbnail more use than a
    // filename", they are the same.
    const groups = groupArtifacts([artifact('a', 'chart'), artifact('b', 'image')]);
    expect(groups).toHaveLength(1);
    expect(groups[0].kind).toBe('gallery');
  });

  it('keeps every artifact, in order', () => {
    // The property that matters most and is easiest to break with a rewrite:
    // grouping is a *presentation* of the list, so nothing may be dropped.
    const input = [
      artifact('a', 'document'),
      artifact('b', 'image'),
      artifact('c', 'image'),
      artifact('d', 'spreadsheet'),
    ];

    const flattened = groupArtifacts(input).flatMap((g) =>
      g.kind === 'gallery' ? g.artifacts : [g.artifact],
    );

    expect(flattened.map((a) => a.id)).toEqual(['a', 'b', 'c', 'd']);
  });
});
