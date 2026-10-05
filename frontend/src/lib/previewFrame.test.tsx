/**
 * @vitest-environment jsdom
 *
 * The check runs what the preview runs. `buildFrameDoc` and the panel assemble
 * the same document in two places; this is the test that says they agree.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

vi.mock('@/services/egressClient', () => ({ recordBrowsed: vi.fn(async () => {}) }));

import CodePreviewPanel from '@/components/chat/CodePreviewPanel';
import { buildFrameDoc } from './previewFrame';
import { extractPreviewable } from './previewableCode';

const FENCE = '```';
afterEach(() => cleanup());

function panelDoc(reply: string): string {
  render(<CodePreviewPanel block={extractPreviewable(reply)!} onClose={() => {}} />);
  return (document.querySelector('iframe') as HTMLIFrameElement).getAttribute('srcdoc') ?? '';
}

describe('the document the check runs', () => {
  it('is the one the preview frame is given, for a single page', async () => {
    const reply = `${FENCE}html\n<html><body><script>var a = 1;</script></body></html>\n${FENCE}`;
    expect(await buildFrameDoc(extractPreviewable(reply)!)).toBe(panelDoc(reply));
  });

  it('is the one the preview frame is given, for an app of modules', async () => {
    const reply =
      `${FENCE}html index.html\n<html><body><script type="module" src="main.js"></script></body></html>\n${FENCE}\n` +
      `${FENCE}js main.js\nimport './a.js';\n${FENCE}\n${FENCE}js a.js\nexport const a = 1;\n${FENCE}\n`;
    const built = await buildFrameDoc(extractPreviewable(reply)!);
    expect(built).toBe(panelDoc(reply));
    // And it is the policy that lets the modules load.
    expect(built).toContain('data:');
  });
});
