/**
 * @vitest-environment jsdom
 *
 * Selecting part of a reply and asking about that part.
 *
 * Asked for 3 October 2026. The transform is tested as a pure function and the
 * wiring is tested through `ChatSurface`, because a tested transform with no
 * caller is this codebase's documented base rate — fifteen complete, tested,
 * unreachable subsystems, and one more found earlier today. A `quoteLines`
 * test alone would prove nothing about whether a selection reaches a prompt.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  CHIP_CHARS,
  MIN_QUOTE_CHARS,
  promptWithQuote,
  QUOTABLE,
  quoteLines,
  useQuotableSelection,
} from './QuoteSelection';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('what goes in front of the question', () => {
  it('prefixes every line', () => {
    expect(quoteLines('one\ntwo')).toBe('> one\n> two');
  });

  it('keeps blank lines as bare markers', () => {
    // Dropping them folds a quoted list into one paragraph, which changes
    // what the person pointed at.
    expect(quoteLines('a\n\nb')).toBe('> a\n>\n> b');
  });

  it('strips the citation markers', () => {
    // `[M1]` is a grounding tag that means nothing outside Zaram, and a
    // quote carrying it sends the model its own labels back. The fifth
    // caller of `stripCitationMarkers`, deliberately not a fresh regex.
    expect(quoteLines('the rate is £400 [M1]')).toBe('> the rate is £400');
  });

  it('is empty for a selection that was only markers and space', () => {
    expect(quoteLines('  [M1] ')).toBe('');
    expect(quoteLines('')).toBe('');
  });

  it('truncates nothing', () => {
    // A selection is the person naming exactly what they mean. Shortening it
    // answers a question they did not ask — the same reasoning that lets
    // somebody pin more tools than the context budget has room for.
    const long = 'x'.repeat(5000);
    expect(quoteLines(long)).toBe(`> ${long}`);
  });

  it('separates the quote from the question with a blank line', () => {
    // Load-bearing: without it markdown folds the question into the
    // blockquote and the model reads its own words and the person's as one
    // passage.
    expect(promptWithQuote('the gate', 'why?')).toBe('> the gate\n\nwhy?');
  });

  it('sends the question alone when there is no quote', () => {
    expect(promptWithQuote('', 'why?')).toBe('why?');
    expect(promptWithQuote('   ', 'why?')).toBe('why?');
  });

  it('keeps the thresholds small enough to be useful', () => {
    // A deliberately selected short word — a name, `npm`, a figure — must
    // still offer, so the mis-click floor cannot creep upwards.
    expect(MIN_QUOTE_CHARS).toBeLessThanOrEqual(3);
    expect(CHIP_CHARS).toBeGreaterThan(40);
  });
});

describe('when a selection counts as quotable', () => {
  /**
   * The rules with real logic in them, against a real DOM and a real Range.
   *
   * Not a mocked `getSelection`: the whole question is whether the *browser's*
   * selection lands inside a region marked quotable, and a stub that returns
   * what the test wants would assert the test's own plumbing.
   */
  function page(html: string) {
    document.body.innerHTML = html;
  }

  function select(startId: string, endId: string) {
    const range = document.createRange();
    range.setStart(document.getElementById(startId)!.firstChild!, 0);
    const end = document.getElementById(endId)!.firstChild!;
    range.setEnd(end, end.textContent!.length);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
    return selection;
  }

  it('offers inside a reply', async () => {
    const { renderHook } = await import('@testing-library/react');
    const { act } = await import('react');
    page(`<div ${QUOTABLE}><p id="a">the gate was waving it through</p></div>`);
    const { result } = renderHook(() => useQuotableSelection());
    act(() => {
      select('a', 'a');
      document.dispatchEvent(new Event('selectionchange'));
    });
    expect(result.current.quotable?.text).toContain('the gate');
  });

  it('offers nothing outside one', async () => {
    const { renderHook } = await import('@testing-library/react');
    const { act } = await import('react');
    // The user's own message, which is deliberately not marked.
    page(`<div><p id="a">what I typed myself</p></div>`);
    const { result } = renderHook(() => useQuotableSelection());
    act(() => {
      select('a', 'a');
      document.dispatchEvent(new Event('selectionchange'));
    });
    expect(result.current.quotable).toBeNull();
  });

  it('offers nothing for a selection that straddles the boundary', async () => {
    const { renderHook } = await import('@testing-library/react');
    const { act } = await import('react');
    // A drag that starts in a reply and finishes in the composer must not
    // offer to quote half the interface.
    page(
      `<div ${QUOTABLE}><p id="a">inside the reply</p></div><div><p id="b">the composer</p></div>`,
    );
    const { result } = renderHook(() => useQuotableSelection());
    act(() => {
      select('a', 'b');
      document.dispatchEvent(new Event('selectionchange'));
    });
    expect(result.current.quotable).toBeNull();
  });

  it('ignores a mis-click', async () => {
    const { renderHook } = await import('@testing-library/react');
    const { act } = await import('react');
    page(`<div ${QUOTABLE}><p id="a">ab</p></div>`);
    const { result } = renderHook(() => useQuotableSelection());
    act(() => {
      select('a', 'a');
      document.dispatchEvent(new Event('selectionchange'));
    });
    expect(result.current.quotable).toBeNull();
  });

  it('stops offering when the selection goes away', async () => {
    const { renderHook } = await import('@testing-library/react');
    const { act } = await import('react');
    page(`<div ${QUOTABLE}><p id="a">the gate was waving it through</p></div>`);
    const { result } = renderHook(() => useQuotableSelection());
    act(() => {
      select('a', 'a');
      document.dispatchEvent(new Event('selectionchange'));
    });
    expect(result.current.quotable).not.toBeNull();
    act(() => {
      window.getSelection()!.removeAllRanges();
      document.dispatchEvent(new Event('selectionchange'));
    });
    expect(result.current.quotable).toBeNull();
  });
});
