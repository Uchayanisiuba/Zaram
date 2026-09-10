/**
 * A reply is markdown, and until 10 September 2026 it was rendered as a string.
 *
 * `whitespace-pre-wrap` around the raw text meant a table arrived as a wall of
 * pipes, a heading as literal hashes, emphasis as asterisks. No model can fix
 * that — every one of them emits correct markdown and it was being discarded
 * at the last step. It is the largest gap between how a reply reads here and
 * how the same reply reads anywhere else, and it is a rendering problem rather
 * than an intelligence one.
 *
 * Two properties here are not cosmetic and are the reason this file exists.
 *
 * **No raw HTML, ever.** Recall folds passages into replies and those passages
 * are written by whoever sent the user the file; `core/untrusted.py` exists
 * because of it. Rendering that text as HTML in the app's own origin is the
 * injection surface the untrusted-content rule is drawn around. The test below
 * asserts the absence rather than trusting a library default to stay the way
 * it is today.
 *
 * **A link is text, not a control.** `electron/main.js` denies every
 * `window.open` and cancels every off-app navigation, so an anchor would look
 * like a link, invite a click and do nothing — which the UI principles forbid:
 * disabled capabilities are visible, not silent.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import MessageBody from './MessageBody';

describe('a reply rendered as the markdown it already is', () => {
  it('renders a table as a table, not as a wall of pipes', () => {
    const reply = [
      '| model | window |',
      '|---|---|',
      '| Tabby | 65536 |',
      '| coder | 32768 |',
    ].join('\n');

    const { container } = render(<MessageBody text={reply} />);

    expect(container.querySelector('table')).not.toBeNull();
    expect(container.querySelectorAll('tbody tr')).toHaveLength(2);
    expect(screen.getByText('65536')).toBeTruthy();
    // The pipes are structure, and structure should not survive as text.
    expect(container.textContent).not.toContain('|---|');
  });

  it('renders headings and emphasis as formatting, not as punctuation', () => {
    const { container } = render(
      <MessageBody text={'## Routing\n\nThis is **important** and *nuanced*.'} />,
    );

    expect(screen.getByText('Routing')).toBeTruthy();
    expect(container.querySelector('strong')?.textContent).toBe('important');
    expect(container.querySelector('em')?.textContent).toBe('nuanced');
    expect(container.textContent).not.toContain('##');
    expect(container.textContent).not.toContain('**');
  });

  it('renders a fenced block as a pre, and inline code inline', () => {
    const { container } = render(
      <MessageBody text={'Run `npm test` first.\n\n```py\nx = 1\n```'} />,
    );

    const fence = container.querySelector('pre');
    expect(fence).not.toBeNull();
    expect(fence?.textContent).toContain('x = 1');
    // Two `code` elements: the inline one and the fenced one.
    expect(container.querySelectorAll('code').length).toBeGreaterThanOrEqual(2);
  });

  it('renders a list as a list', () => {
    const { container } = render(<MessageBody text={'- one\n- two\n- three'} />);

    expect(container.querySelectorAll('li')).toHaveLength(3);
    expect(container.textContent).not.toContain('- one');
  });

  /**
   * The one that matters. A recalled passage is third-party text, and this is
   * the difference between a formatting feature and an injection surface.
   */
  it('never renders raw HTML from a reply', () => {
    const hostile =
      'Here is a quote from the file: <img src=x onerror="alert(1)"> and ' +
      '<script>fetch("http://elsewhere")</script> plus <b>bold</b>.';

    const { container } = render(<MessageBody text={hostile} />);

    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
    // `<b>` is harmless and still must not be honoured: allowing "safe" tags
    // is how an allow-list becomes a guess about what is safe.
    expect(container.querySelector('b')).toBeNull();
  });

  it('shows where a link points instead of pretending it can be followed', () => {
    const { container } = render(
      <MessageBody text={'See [the docs](https://example.com/page) for more.'} />,
    );

    expect(container.querySelector('a')).toBeNull();
    expect(container.textContent).toContain('the docs');
    expect(container.textContent).toContain('https://example.com/page');
  });

  it('highlights a fence that names its language', () => {
    const { container } = render(
      <MessageBody
        text={['```python', 'def f():', '    return "x"', '```'].join('\n')}
      />,
    );

    expect(container.querySelector('.hljs-keyword')?.textContent).toBe('def');
    expect(container.querySelector('.hljs-string')).not.toBeNull();
  });

  /**
   * `detect: false` is a decision rather than a default.
   *
   * With detection on, highlight.js guesses at every unlabelled fence, and a
   * wrong guess colours words as keywords that are not keywords — a confident
   * wrong answer rendered into the interface, which the UI principles rule out
   * for status indicators and which is no better here.
   */
  it('leaves an unlabelled fence unguessed', () => {
    const { container } = render(
      <MessageBody text={['```', 'def f(): return 1', '```'].join('\n')} />,
    );

    expect(container.querySelector('pre')).not.toBeNull();
    expect(container.querySelector('.hljs-keyword')).toBeNull();
    expect(container.textContent).toContain('def f(): return 1');
  });

  it('renders a fence in a language nobody registered rather than throwing', () => {
    const { container } = render(
      <MessageBody text={['```notalanguage', 'some text', '```'].join('\n')} />,
    );

    expect(container.querySelector('pre')?.textContent).toContain('some text');
  });

  it('leaves an ordinary reply looking ordinary', () => {
    const { container } = render(
      <MessageBody text={'Routed to qwen3 — a coding question.'} />,
    );

    expect(container.textContent).toBe('Routed to qwen3 — a coding question.');
  });
});
