/**
 * A row of web citations has to tell you which is which.
 *
 * Before this, a cited page rendered as a globe and a number — so four sources
 * were four identical glyphs, and the one fact that distinguishes them, who
 * published the page, was reachable only by opening the panel on each in turn.
 * A source row is scanned rather than read, and a mark that is the same on
 * every entry carries nothing.
 *
 * **Text rather than a favicon, and that is the decision rather than a
 * stopgap.** A favicon is fetched from the site, which is a request
 * `EgressGate` structurally cannot see and `check-no-remote-assets.mjs` bans
 * outright; worse, it would fire on every *render*, so reopening a
 * conversation next week pings the publisher again. The domain is also the
 * better signal: it is legible where a 16px mark is a guess, and it does not
 * lend a content farm the authority of a well-drawn logo.
 *
 * The colour rule is untouched and is asserted here so it stays that way: cyan
 * for what stayed, violet for what left. Naming the site must not become a
 * second, quieter way of saying the same thing.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

import CitationSummary, { CitationChip } from './CitationChips';
import { hostOf, type ChatSource } from '@/services/chatClient';

function source(over: Partial<ChatSource> = {}): ChatSource {
  return {
    kind: 'web',
    url: 'https://www.freightwaves.com/news/lagos-port',
    title: 'Lagos port expansion',
    excerpt: '',
    relevance: 0.8,
    cited: true,
    number: 1,
    egressId: 'e1',
    bytesSent: 400,
    origin: 'web',
    recordId: null,
    ...over,
  };
}

afterEach(cleanup);

describe('the site is on the chip', () => {
  it('names the domain of a cited page', () => {
    render(<CitationChip source={source()} onOpen={vi.fn()} />);

    expect(screen.getByText('freightwaves.com')).toBeTruthy();
  });

  it('drops www., which is on every domain that has it and no domain that does not', () => {
    expect(hostOf('https://www.nytimes.com/a')).toBe('nytimes.com');
  });

  it('keeps a subdomain, which is part of who published it', () => {
    /** `docs.example.com` and `blog.example.com` are not interchangeable. */
    expect(hostOf('https://docs.example.com/a')).toBe('docs.example.com');
  });

  it('says nothing for a source that is not a web page', () => {
    render(
      <CitationChip
        source={source({ kind: 'memory', url: 'memory:abc', origin: 'conversation' })}
        onOpen={vi.fn()}
      />,
    );

    expect(screen.queryByText(/\./)).toBeNull();
  });

  it('invents no domain from a malformed URL', () => {
    /** A name on a chip that links somewhere else is worse than no name. */
    expect(hostOf('https://')).toBeNull();
    expect(hostOf('not a url')).toBeNull();
    expect(hostOf('')).toBeNull();
  });

  it('reaches a screen reader too, not only the eye', () => {
    render(<CitationChip source={source()} onOpen={vi.fn()} />);

    expect(
      screen.getByLabelText(/Source 1:.*freightwaves\.com/i),
    ).toBeTruthy();
  });
});

describe('what naming the site must not change', () => {
  it('still colours by whether the source left the device', () => {
    const { container } = render(<CitationChip source={source()} onOpen={vi.fn()} />);
    const web = container.querySelector('button')!;

    cleanup();
    const local = render(
      <CitationChip
        source={source({ kind: 'memory', url: 'memory:abc' })}
        onOpen={vi.fn()}
      />,
    ).container.querySelector('button')!;

    // Violet for what left, cyan for what stayed — the orb's two colours,
    // reused so they need no legend. Matched loosely on the channels because
    // the DOM re-serialises `rgb(...)` with its own spacing, and this test is
    // about which colour was chosen rather than how it was written.
    expect(web.getAttribute('style')).toMatch(/196,\s*152,\s*252/);
    expect(local.getAttribute('style')).toMatch(/120,\s*220,\s*240/);
  });

  it('still leads the summary with the egress split', () => {
    render(
      <CitationSummary
        sources={[source(), source({ number: 2, url: 'https://nytimes.com/b' })]}
        deleted={new Set()}
        onOpenPanel={vi.fn()}
        onOpenSource={vi.fn()}
      />,
    );

    expect(screen.getByText(/2 sent to the web/)).toBeTruthy();
  });

  it('fetches nothing to draw a chip', () => {
    /** The guarantee behind choosing text over a favicon, asserted rather than
     *  described: rendering a citation must not touch the network, because a
     *  request made by the renderer is one no gate can see. */
    const fetchSpy = vi.spyOn(globalThis, 'fetch');

    render(<CitationChip source={source()} onOpen={vi.fn()} />);

    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});
