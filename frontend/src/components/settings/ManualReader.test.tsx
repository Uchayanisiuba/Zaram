import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ManualReader from './ManualReader';

const INDEX = {
  pages: [
    { slug: 'what-zaram-is', title: 'What Zaram is', order: 1 },
    { slug: 'memory', title: 'Memory', order: 4 },
  ],
  version: 'abc',
  indexedVersion: 'abc',
};

const PAGES: Record<string, string> = {
  'what-zaram-is': '# What Zaram is\n\nZaram is an assistant that remembers you.\n\n![The landing](/manual/assets/landing.png)',
  memory: '# Memory\n\nTo export your memory, open **Settings → Export**.',
};

describe('the manual', () => {
  it('lists the pages, opens the first, and shows its pictures from the backend', async () => {
    // Fetched through the app's own fetch -- the one that carries the credential --
    // and shown from memory. A bare <img src> to the backend is refused with a 401,
    // which is how every manual picture came to show only its caption.
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => new Response(new Blob(['png'], { type: 'image/png' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const createObjectURL = vi.fn(() => 'blob:manual-landing');
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
    render(<ManualReader onClose={vi.fn()} load={vi.fn().mockResolvedValue(INDEX)} loadPage={vi.fn(async (s: string) => PAGES[s])} />);
    expect(await screen.findByRole('heading', { name: 'What Zaram is' })).toBeInTheDocument();
    const img = (await screen.findByRole('img', { name: 'The landing' })) as HTMLImageElement;
    expect(String(fetchMock.mock.calls[0][0])).toContain('/manual/assets/landing.png');
    expect(img.src).toBe('blob:manual-landing');
    expect(screen.getByText('The landing')).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it('says so when a picture cannot be loaded, rather than leaving a blank', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('no', { status: 401 })));
    render(<ManualReader onClose={vi.fn()} load={vi.fn().mockResolvedValue(INDEX)} loadPage={vi.fn(async (s: string) => PAGES[s])} />);
    expect(await screen.findByText('The picture could not be loaded.')).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it('turns to another page', async () => {
    render(<ManualReader onClose={vi.fn()} load={vi.fn().mockResolvedValue(INDEX)} loadPage={vi.fn(async (s: string) => PAGES[s])} />);
    await screen.findByRole('heading', { name: 'What Zaram is' });
    await userEvent.click(screen.getByTestId('manual-page-memory'));
    expect(await screen.findByRole('heading', { name: 'Memory' })).toBeInTheDocument();
    expect(screen.getByText(/export your memory/i)).toBeInTheDocument();
  });

  it('says when the domain has not caught up with the pages', async () => {
    render(
      <ManualReader onClose={vi.fn()} load={vi.fn().mockResolvedValue({ ...INDEX, indexedVersion: 'old' })} loadPage={vi.fn(async (s: string) => PAGES[s])} />,
    );
    expect(await screen.findByText(/still reading the new pages/i)).toBeInTheDocument();
  });

  it('closes on the button and on Escape', async () => {
    const onClose = vi.fn();
    render(<ManualReader onClose={onClose} load={vi.fn().mockResolvedValue(INDEX)} loadPage={vi.fn(async (s: string) => PAGES[s])} />);
    await screen.findByRole('heading', { name: 'What Zaram is' });
    await userEvent.click(screen.getByRole('button', { name: /close the manual/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
    await userEvent.keyboard('{Escape}');
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(2));
  });

  it('a failure to read is said', async () => {
    render(<ManualReader onClose={vi.fn()} load={vi.fn().mockRejectedValue(new Error('503 Service Unavailable'))} />);
    expect(await screen.findByText('503 Service Unavailable')).toBeInTheDocument();
  });
});
