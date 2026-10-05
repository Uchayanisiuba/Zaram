/**
 * The document the preview frame runs, built without the panel.
 *
 * The page check (`core/page_check.py`) has to load exactly what the preview
 * would, or it passes pages the preview then breaks: the same policy, the same
 * shims, the same vendored three.js. `CodePreviewPanel` builds this inside
 * hooks because it waits on the library and re-renders as a reply streams;
 * this is the same assembly for a caller that has the finished reply and
 * nothing to render. If one changes, change both -- `previewFrame.test.ts`
 * compares them.
 */
import { loadThree, usesThree, vendorPage } from './previewLibraries';
import { wrapForPreview, type PreviewableBlock } from './previewableCode';

export async function buildFrameDoc(block: PreviewableBlock): Promise<string> {
  const everything = block.files ? block.files.map((f) => f.code).join('\n') : block.code;
  let vendored: ReturnType<typeof vendorPage> = null;
  if (usesThree(everything)) {
    try {
      vendored = vendorPage(block.code, await loadThree(), block.files ? everything : '');
    } catch {
      // The library would not load. The page is checked as written, which
      // reports the failure the panel would have shown.
    }
  }
  return wrapForPreview(
    vendored ? vendored.body : block.code,
    'app',
    [],
    (vendored?.prefix ?? '') || (block.modules ? "<!-- the app's modules -->" : ''),
  );
}
