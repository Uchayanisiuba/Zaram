/**
 * @vitest-environment jsdom
 *
 * An app of several files, run and kept without a project — 5 October 2026.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('@/services/egressClient', () => ({ recordBrowsed: vi.fn(async () => {}) }));

import CodePreviewPanel from './CodePreviewPanel';
import { extractPreviewable } from '@/lib/previewableCode';

const FENCE = '```';
const reply =
  `${FENCE}html index.html\n<html><head><link rel="stylesheet" href="style.css"></head><body><script src="game.js"></script></body></html>\n${FENCE}\n` +
  `${FENCE}css style.css\nbody{background:#123456}\n${FENCE}\n` +
  `${FENCE}js game.js\nwindow.started = true;\n${FENCE}\n`;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('a reply with several named files', () => {
  it('is one previewable thing, already joined', () => {
    const block = extractPreviewable(reply)!;
    expect(block.label).toBe('App');
    expect(block.files?.map((f) => f.path)).toEqual(['index.html', 'style.css', 'game.js']);
    expect(block.code).toContain('background:#123456');
    expect(block.code).toContain('window.started = true;');
  });

  it('runs the joined page in the sealed frame', () => {
    render(<CodePreviewPanel block={extractPreviewable(reply)!} onClose={() => {}} />);
    const doc = (document.querySelector('iframe') as HTMLIFrameElement).getAttribute('srcdoc') ?? '';
    expect(doc).toContain('background:#123456');
    expect(doc).toContain('window.started = true;');
  });

  it('shows every file when the code is read', () => {
    render(<CodePreviewPanel block={extractPreviewable(reply)!} onClose={() => {}} />);
    fireEvent.click(screen.getByTestId('view-code'));
    const shown = screen.getByTestId('preview-code').textContent ?? '';
    expect(shown).toContain('index.html');
    expect(shown).toContain('style.css');
    expect(shown).toContain('game.js');
  });

  it('names the file a never-ending loop is in', () => {
    const looping = reply.replace('window.started = true;', 'for (let i = 0; i < 9; i) { draw(i); }');
    render(<CodePreviewPanel block={extractPreviewable(looping)!} onClose={() => {}} onAsk={vi.fn()} />);
    expect(screen.getByTestId('stuck-loop').textContent).toContain('game.js, line 1');
  });

  it('is saved as a folder through the backend, and says where', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ path: 'C:/out/apps/app' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<CodePreviewPanel block={extractPreviewable(reply)!} onClose={() => {}} />);
    fireEvent.click(screen.getByLabelText(/^Save as/));
    await waitFor(() => expect(screen.getByTestId('save-note').textContent).toContain('C:/out/apps/app'));
    const call = fetchMock.mock.calls[0] as unknown as [string, { body: string }];
    expect(call[0]).toContain('/apps/save');
    expect(JSON.parse(call[1].body).files.map((f: { path: string }) => f.path)).toEqual([
      'index.html',
      'style.css',
      'game.js',
    ]);
  });

  it('says why when the backend refuses', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'not a path' }), { status: 400 })));
    render(<CodePreviewPanel block={extractPreviewable(reply)!} onClose={() => {}} />);
    fireEvent.click(screen.getByLabelText(/^Save as/));
    await waitFor(() => expect(screen.getByTestId('save-note').textContent).toContain('Not saved: not a path'));
  });
});
