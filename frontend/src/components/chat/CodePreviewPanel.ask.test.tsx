/**
 * @vitest-environment jsdom
 *
 * Asking Zaram about the page from inside the preview — 5 October 2026.
 *
 * *Select* points at part of the page and asks for a change; *Fix this* hands
 * a page that stopped back with its error. Both go to `onAsk`, which the
 * conversation sends as a revision of the reply that wrote the page.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

vi.mock('@/services/egressClient', () => ({ recordBrowsed: vi.fn(async () => {}) }));

import CodePreviewPanel from './CodePreviewPanel';

const block = { language: 'html', label: 'HTML', code: '<button id="start">Start</button>' };

function frame(): HTMLIFrameElement {
  return document.querySelector('iframe') as HTMLIFrameElement;
}

function fromFrame(data: Record<string, unknown>) {
  act(() => {
    window.dispatchEvent(new MessageEvent('message', { data: { __zaramPreview: true, ...data }, source: frame().contentWindow }));
  });
}

const picked = {
  tag: 'button',
  selector: 'body > div#overlay > button#start',
  text: 'Start',
  html: '<button id="start">Start</button>',
  rect: { x: 40, y: 60, w: 80, h: 24 },
};

afterEach(() => cleanup());

describe('Select', () => {
  it('is offered only where there is a conversation to ask', () => {
    render(<CodePreviewPanel block={block} onClose={() => {}} />);
    expect(screen.queryByTestId('pick-toggle')).toBeNull();
  });

  it('tells the frame when it turns on and off', () => {
    render(<CodePreviewPanel block={block} onClose={() => {}} onAsk={vi.fn()} />);
    const post = vi.spyOn(frame().contentWindow as Window, 'postMessage');

    fireEvent.click(screen.getByTestId('pick-toggle'));
    expect(screen.getByTestId('pick-toggle').getAttribute('aria-pressed')).toBe('true');
    expect(post).toHaveBeenLastCalledWith({ __zaramPreviewControl: true, action: 'pick', on: true }, '*');
    expect(screen.getByTestId('pick-hint')).toBeTruthy();

    fireEvent.click(screen.getByTestId('pick-toggle'));
    expect(post).toHaveBeenLastCalledWith({ __zaramPreviewControl: true, action: 'pick', on: false }, '*');
  });

  it('asks about the part that was picked, for the whole page back', () => {
    const onAsk = vi.fn();
    render(<CodePreviewPanel block={block} onClose={() => {}} onAsk={onAsk} />);
    fireEvent.click(screen.getByTestId('pick-toggle'));

    fromFrame({ kind: 'picked', detail: JSON.stringify(picked) });

    expect(screen.getByTestId('ask-popover').textContent).toContain('button#start');
    fireEvent.change(screen.getByTestId('ask-input'), { target: { value: 'make it red' } });
    fireEvent.click(screen.getByTestId('ask-send'));

    const sent = onAsk.mock.calls[0][0] as string;
    expect(sent).toContain('What to change: make it red');
    expect(sent).toContain('body > div#overlay > button#start');
    expect(sent).toContain('whole updated page');
    // Picking ends with the question sent.
    expect(screen.queryByTestId('ask-popover')).toBeNull();
  });

  it('Escape closes the question before it closes anything else', () => {
    const onClose = vi.fn();
    render(<CodePreviewPanel block={block} onClose={onClose} onAsk={vi.fn()} />);
    fireEvent.click(screen.getByTestId('pick-toggle'));
    fromFrame({ kind: 'picked', detail: JSON.stringify(picked) });

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByTestId('ask-popover')).toBeNull();
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.getByTestId('pick-toggle').getAttribute('aria-pressed')).toBe('false');
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('ignores a pick that does not come from this frame', () => {
    render(<CodePreviewPanel block={block} onClose={() => {}} onAsk={vi.fn()} />);
    window.dispatchEvent(
      new MessageEvent('message', { data: { __zaramPreview: true, kind: 'picked', detail: JSON.stringify(picked) }, source: window }),
    );
    expect(screen.queryByTestId('ask-popover')).toBeNull();
  });
});

describe('Fix this', () => {
  it('appears when the page stops, and hands the error back', () => {
    const onAsk = vi.fn();
    render(<CodePreviewPanel block={block} onClose={() => {}} onAsk={onAsk} />);
    expect(screen.queryByTestId('fix-this')).toBeNull();

    fromFrame({ kind: 'error', detail: 'Uncaught ReferenceError: THREE is not defined' });
    fireEvent.click(screen.getByTestId('fix-this'));

    const sent = onAsk.mock.calls[0][0] as string;
    expect(sent).toContain('THREE is not defined');
    expect(sent).toContain('whole page');
  });
});

describe('a page with a loop that cannot end', () => {
  const stuck = { language: 'html', label: 'HTML', code: '<script>for(let i=0;i<16;i)for(let j=0;j<16;j++){}</script>' };

  it('is not started, and says where', () => {
    render(<CodePreviewPanel block={stuck} onClose={() => {}} onAsk={vi.fn()} />);
    expect(screen.getByTestId('stuck-loop').textContent).toContain('Line 1');
    expect(frame().hidden).toBe(true);
    expect(frame().getAttribute('srcdoc') ?? '').toBe('');
  });

  it('Fix this sends the line back to be fixed', () => {
    const onAsk = vi.fn();
    render(<CodePreviewPanel block={stuck} onClose={() => {}} onAsk={onAsk} />);
    fireEvent.click(screen.getByTestId('stuck-fix'));
    const sent = onAsk.mock.calls[0][0] as string;
    expect(sent).toContain('for(let i=0;i<16;i)');
    expect(sent).toContain('whole page');
  });

  it('Run anyway starts it', () => {
    render(<CodePreviewPanel block={stuck} onClose={() => {}} onAsk={vi.fn()} />);
    fireEvent.click(screen.getByTestId('stuck-run'));
    expect(screen.queryByTestId('stuck-loop')).toBeNull();
    expect(frame().hidden).toBe(false);
    expect(frame().getAttribute('srcdoc') ?? '').toContain('for(let i=0;i<16;i)');
  });

  it('a corrected page runs without being asked', () => {
    render(<CodePreviewPanel block={{ ...stuck, code: stuck.code.replace('i)', 'i++)') }} onClose={() => {}} onAsk={vi.fn()} />);
    expect(screen.queryByTestId('stuck-loop')).toBeNull();
    expect(frame().getAttribute('srcdoc') ?? '').toContain('i++');
  });
});
