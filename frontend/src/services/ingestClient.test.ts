/**
 * @vitest-environment node
 *
 * Ingest transport — the three ways in, and what the user is told when one fails.
 *
 * Node rather than jsdom: this is fetch, FormData and streams, not the DOM.
 *
 * The two assertions worth having are the ones that would be silently wrong.
 * A multipart body without the browser's own boundary is unparseable at the
 * other end, and setting `Content-Type` by hand is exactly how that happens —
 * so the absence of that header is asserted rather than assumed. And a refusal
 * has to arrive carrying the backend's sentence, because "413" is not something
 * a person can act on and "that file is larger than 100 MB" is.
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { ingestFolder, ingestText, uploadFiles, type IngestEvent } from './ingestClient';

const line = (o: unknown) => JSON.stringify(o) + '\n';

function streamingResponse(chunks: string[], init: ResponseInit = {}) {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c));
      controller.close();
    },
  });
  return new Response(body, { status: 200, ...init });
}

const DONE = { type: 'done', source_id: 'src-1', root: '/uploads', total: 1, problems: 0 };

afterEach(() => vi.unstubAllGlobals());

/** The last request `fetch` was called with. */
function capture(response: Response) {
  const calls: { url: string; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      return response;
    }),
  );
  return calls;
}

describe('uploadFiles', () => {
  it('sends the files as multipart and lets the browser set the boundary', async () => {
    const calls = capture(streamingResponse([line(DONE)]));

    await uploadFiles([new File(['a brief'], 'brief.txt', { type: 'text/plain' })], () => {});

    expect(calls[0].url).toContain('/ingest/upload');
    expect(calls[0].init.body).toBeInstanceOf(FormData);
    // The boundary lives in the header the browser generates. Naming the type
    // by hand omits it, and the body arrives unparseable.
    expect(calls[0].init.headers).toBeUndefined();

    const sent = calls[0].init.body as FormData;
    expect(sent.getAll('files')).toHaveLength(1);
  });

  it('reports every file event as it arrives', async () => {
    capture(
      streamingResponse([
        line({ type: 'start', root: '/uploads', total: 2 }),
        line({ type: 'file', index: 1, total: 2, name: 'one.txt', status: 'indexed' }),
        line({ type: 'file', index: 2, total: 2, name: 'two.pdf', status: 'empty' }),
        line(DONE),
      ]),
    );

    const seen: IngestEvent[] = [];
    await uploadFiles([new File(['x'], 'one.txt')], (event) => seen.push(event));

    expect(seen.map((e) => e.type)).toEqual(['start', 'file', 'file', 'done']);
  });

  it('carries the refusal the backend wrote, not its status code', async () => {
    capture(
      new Response(JSON.stringify({ detail: 'huge.iso is larger than 100 MB.' }), { status: 413 }),
    );

    await expect(uploadFiles([new File(['x'], 'huge.iso')], () => {})).rejects.toThrow(
      'huge.iso is larger than 100 MB.',
    );
  });

  it('still says something when a failure has no body', async () => {
    capture(new Response('', { status: 502, statusText: 'Bad Gateway' }));

    await expect(uploadFiles([new File(['x'], 'a.txt')], () => {})).rejects.toThrow(/502/);
  });
});

describe('ingestText', () => {
  it('posts the text and its name as JSON', async () => {
    const calls = capture(streamingResponse([line(DONE)]));

    await ingestText('Northwind agreed to 450 a day.', 'call notes', () => {});

    expect(calls[0].url).toContain('/ingest/text');
    expect(JSON.parse(calls[0].init.body as string)).toEqual({
      text: 'Northwind agreed to 450 a day.',
      name: 'call notes',
    });
  });

  it('carries the refusal for an empty paste', async () => {
    capture(new Response(JSON.stringify({ detail: 'There was nothing in that.' }), { status: 400 }));

    await expect(ingestText('   ', '', () => {})).rejects.toThrow('There was nothing in that.');
  });
});

describe('every way in', () => {
  /** One stream reader, so a split-chunk fix lands in all three at once. */
  it('decodes an object split across chunk boundaries', async () => {
    const whole = line({ type: 'file', index: 1, total: 1, name: 'split.txt', status: 'indexed' });
    capture(streamingResponse([whole.slice(0, 20), whole.slice(20), line(DONE)]));

    const seen: IngestEvent[] = [];
    await ingestFolder('/docs', (event) => seen.push(event));

    expect(seen.map((e) => e.type)).toEqual(['file', 'done']);
    expect((seen[0] as { name: string }).name).toBe('split.txt');
  });

  it('survives a malformed line rather than losing the run', async () => {
    capture(streamingResponse(['{not json\n', line(DONE)]));

    const seen: IngestEvent[] = [];
    await uploadFiles([new File(['x'], 'a.txt')], (event) => seen.push(event));

    // The `done` event carries the authoritative totals either way.
    expect(seen.map((e) => e.type)).toEqual(['done']);
  });
});
