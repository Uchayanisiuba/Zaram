/**
 * Rows sit where they happened, and the prose is not reordered around them.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import Interleaved, { segments } from './Interleaved';
import type { ChatToolCall } from '@/stores/chatStore';

const row = (over: Partial<ChatToolCall>): ChatToolCall => ({
  server: 'code',
  tool: 'read_lines',
  verdict: 'allow',
  reason: 'ran',
  target: 'store.ts',
  ...over,
});

describe('segments', () => {
  it('cuts the text at the offsets the rows arrived at, in order', () => {
    const text = "I'll read the store first. The reducer is in store.ts. Done.";
    const first = text.indexOf(' The reducer');
    const second = text.indexOf(' Done.');
    const out = segments(text, [row({ at: second, tool: 'edit_file' }), row({ at: first })]);
    expect(out.map((s) => s.kind)).toEqual(['text', 'rows', 'text', 'rows', 'text']);
    expect(out[0].text).toBe("I'll read the store first.");
    expect(out[1].calls?.[0].tool).toBe('read_lines');
    expect(out[2].text).toBe(' The reducer is in store.ts.');
    expect(out[3].calls?.[0].tool).toBe('edit_file');
    expect(out[4].text).toBe(' Done.');
  });

  it('puts rows with no offset in front, where a restored history has them', () => {
    const out = segments('answer', [row({}), row({ tool: 'search_code' })]);
    expect(out.map((s) => s.kind)).toEqual(['rows', 'text']);
    expect(out[0].calls).toHaveLength(2);
  });

  it('clamps an offset past the end to the end, and drops empty chunks', () => {
    const out = segments('short', [row({ at: 999 })]);
    expect(out.map((s) => s.kind)).toEqual(['text', 'rows']);
    expect(segments('', [row({ at: 0 })]).map((s) => s.kind)).toEqual(['rows']);
    expect(segments('only text', [])).toEqual([{ kind: 'text', text: 'only text' }]);
  });
});

describe('Interleaved', () => {
  it('renders each chunk through the caller and each group as rows, in order', () => {
    const text = 'before. after.';
    render(
      <Interleaved
        text={text}
        calls={[row({ at: text.indexOf(' after') })]}
        renderText={(chunk, last) => <p data-testid={last ? 'last-chunk' : 'chunk'}>{chunk}</p>}
      />,
    );
    const nodes = [...screen.getByTestId('interleaved').children].map((n) => n.getAttribute('data-testid'));
    expect(nodes[0]).toBeNull(); // the wrapper div around the first chunk
    expect(screen.getByTestId('chunk').textContent).toBe('before.');
    expect(screen.getByTestId('last-chunk').textContent).toBe(' after.');
    expect(screen.getByTestId('tool-calls')).toBeTruthy();
    // Order on screen: chunk, rows, chunk.
    const order = [...document.querySelectorAll('[data-testid="chunk"], [data-testid="tool-calls"], [data-testid="last-chunk"]')].map((n) => n.getAttribute('data-testid'));
    expect(order).toEqual(['chunk', 'tool-calls', 'last-chunk']);
  });
});
