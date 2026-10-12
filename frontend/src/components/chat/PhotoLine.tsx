import { isFound, photoNotes } from '@/lib/pagePhotos';
import type { PreviewableBlock } from '@/lib/previewableCode';

/**
 * Where the page's photographs stand, said under the reply.
 *
 * A page with `photo:` descriptions is not finished when the reply is: the
 * photographs are still being looked for, and the first search waits for the
 * person to say yes. So the wait is named, and so is the outcome -- found and
 * credited, or not found and why -- rather than a page that quietly fills in
 * or quietly does not. Nothing is shown for a page without photographs.
 */
export default function PhotoLine({ block }: { block: PreviewableBlock }) {
  const total = block.photoRefs ?? 0;
  if (!total) return null;
  const entries = Object.values(block.photos ?? {});
  const found = entries.filter(isFound).length;

  let text: string;
  if (entries.length < Math.min(total, 8)) {
    text = `Finding photos for the page (${found} of ${Math.min(total, 8)})… Each photo source asks you the first time.`;
  } else {
    const notes = photoNotes(block);
    const foundLine = found
      ? `${found} ${found === 1 ? 'photo' : 'photos'} found online, openly licensed and credited at the foot of the page.`
      : '';
    text = [foundLine, ...notes].filter(Boolean).join(' ');
  }
  return (
    <p
      role="status"
      data-testid="photo-line"
      className="mt-1 w-full text-xs"
      style={{ color: 'var(--color-text-muted)', margin: '4px 0 0' }}
    >
      {text}
    </p>
  );
}
