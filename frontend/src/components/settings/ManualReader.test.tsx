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
    render(<ManualReader onClose={vi.fn()} load={vi.fn().mockResolvedValue(INDEX)} loadPage={vi.fn(async (s: string) => PAGES[s])} />);
    expect(await screen.findByRole('heading', { name: 'What Zaram is' })).toBeInTheDocument();
    const img = screen.getByRole('img', { name: 'The landing' }) as HTMLImageElement;
    expect(img.src).toContain('/manual/assets/landing.png');
    expect(screen.getByText('The landing')).toBeInTheDocument();
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
