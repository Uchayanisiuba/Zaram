/**
 * @vitest-environment jsdom
 *
 * Citations restored as history.
 *
 * A reopened conversation draws its citations from references the backend
 * resolved against the Spine as it is now. What matters on screen:
 *
 * * A fact **deleted since** is drawn like one forgotten just now, and said in
 *   words — a struck chip is a mark, not a sentence.
 * * A fact **corrected since** is marked differently: the answer was written
 *   from wording the fact no longer has, which is not the same as it being gone.
 * * **`unchecked` is never drawn as deleted.** The lookup could not be made;
 *   claiming a deletion would be an invented value about the person's data.
 * * A live citation, which carries no `history`, is unchanged.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import type { ChatSource } from '@/services/chatClient';
import CitationSummary, { CitationChip } from './CitationChips';

const source = (over: Partial<ChatSource> = {}): ChatSource => ({
  kind: 'memory',
  url: 'memory:fact-1',
  title: null,
  excerpt: null,
  relevance: 0.8,
  cited: true,
  number: 1,
  egressId: null,
  bytesSent: null,
  origin: 'conversation',
  recordId: 'fact-1',
  ...over,
});

afterEach(() => cleanup());

const chip = (s: ChatSource) =>
  render(<CitationChip source={s} onOpen={vi.fn()} />).getByRole('button');

describe('the chip', () => {
  it('draws a fact deleted since as struck through, and says so', () => {
    const el = chip(source({ history: { state: 'deleted' } }));
    expect(el.style.textDecoration).toContain('line-through');
    expect(el.title).toContain('deleted since this answer');
  });

  it('marks a corrected fact differently from a deleted one', () => {
    const el = chip(source({ history: { state: 'corrected' } }));
    expect(el.style.textDecoration).not.toContain('line-through');
    expect(el.style.textDecoration).toContain('underline');
    expect(el.title).toContain('corrected since this answer');
  });

  it('draws an unchecked citation as nothing special — never as deleted', () => {
    const el = chip(source({ history: { state: 'unchecked' } }));
    expect(el.style.textDecoration).toBe('none');
    expect(el.title).not.toContain('deleted');
    expect(el.title).not.toContain('corrected');
  });

  it('draws a live restored citation as an ordinary one', () => {
    const el = chip(source({ history: { state: 'live' } }));
    expect(el.style.textDecoration).toBe('none');
  });

  it('draws a recorded web page as an ordinary one', () => {
    const el = chip(source({ kind: 'web', url: 'https://example.com/a', history: { state: 'recorded' } }));
    expect(el.style.textDecoration).toBe('none');
  });

  it('leaves a live citation, which has no history, untouched', () => {
    const el = chip(source());
    expect(el.style.textDecoration).toBe('none');
    expect(el.getAttribute('data-history')).toBeNull();
  });

  it('still honours a fact forgotten just now', () => {
    const { getByRole } = render(<CitationChip source={source()} onOpen={vi.fn()} forgotten />);
    expect(getByRole('button').title).toContain('forgotten');
  });
});

describe('the summary line', () => {
  const summary = (sources: ChatSource[]) =>
    render(
      <CitationSummary
        sources={sources}
        deleted={new Set()}
        onOpenPanel={vi.fn()}
        onOpenSource={vi.fn()}
      />,
    );

  it('says in words how many changed since', () => {
    summary([
      source({ history: { state: 'deleted' } }),
      source({ url: 'memory:fact-2', number: 2, history: { state: 'corrected' } }),
      source({ url: 'memory:fact-3', number: 3, history: { state: 'live' } }),
    ]);
    expect(screen.getByTestId('history-segment')).toHaveTextContent('1 deleted since, 1 corrected since');
  });

  it('says nothing when nothing changed', () => {
    summary([source({ history: { state: 'live' } }), source({ url: 'memory:fact-2', number: 2 })]);
    expect(screen.queryByTestId('history-segment')).toBeNull();
  });

  it('does not count unchecked as a change', () => {
    summary([source({ history: { state: 'unchecked' } })]);
    expect(screen.queryByTestId('history-segment')).toBeNull();
  });
});
