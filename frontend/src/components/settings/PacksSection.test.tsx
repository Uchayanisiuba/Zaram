import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { Extra, InstallEvent } from '@/services/extrasClient';
import PacksSection, { PackOffer } from './PacksSection';

function Row({
  label,
  value,
  detail,
  children,
}: {
  label: string;
  value?: string;
  detail?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div>
      <span>{label}</span>
      {value && <em>{value}</em>}
      <div>{detail}</div>
      {children}
    </div>
  );
}

const MIC: Extra = {
  id: 'mic',
  name: 'Listening',
  enables: ['Push-to-talk and hands-free listening, transcribed on this machine.'],
  sizeMb: 81,
  measured: 'wheels downloaded, 10 August 2026',
  installed: false,
  restart: false,
};
const VOICE: Extra = { ...MIC, id: 'voice', name: 'Speaking', sizeMb: 290, restart: true };

describe('Packs', () => {
  it('lists each pack with what it turns on, its cost, and one button', async () => {
    render(<PacksSection Row={Row} load={vi.fn().mockResolvedValue([MIC, { ...VOICE, installed: true }])} />);
    expect(await screen.findByText('Listening')).toBeInTheDocument();
    expect(screen.getAllByText(/push-to-talk and hands-free/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/81 MB, measured wheels downloaded, 10 August/i)).toBeInTheDocument();
    expect(screen.getByTestId('pack-mic-get')).toHaveTextContent('Get it — 81 MB, one time');
    expect(screen.getByTestId('pack-voice-done')).toHaveTextContent('installed');
    expect(screen.queryByTestId('pack-voice-get')).not.toBeInTheDocument();
  });

  it('shows the installer’s own lines and says when a restart is needed', async () => {
    const install = vi.fn(async (_id: string, onEvent: (e: InstallEvent) => void) => {
      onEvent({ stage: 'Getting the Speaking pack — about 290 MB, one time.' });
      onEvent({ line: 'Collecting kokoro' });
      const terminal: InstallEvent = { done: true, restart: true };
      onEvent(terminal);
      return terminal;
    });
    render(<PacksSection Row={Row} load={vi.fn().mockResolvedValue([VOICE])} install={install} />);
    await userEvent.click(await screen.findByTestId('pack-voice-get'));
    await waitFor(() => expect(screen.getByTestId('pack-voice-done')).toHaveTextContent(/restart Zaram/i));
    expect(install).toHaveBeenCalledWith('voice', expect.any(Function));
  });

  it('a failed install is a sentence and the button stays', async () => {
    const install = vi.fn().mockResolvedValue({ error: 'The Listening pack did not install: exited with 1' });
    render(<PacksSection Row={Row} load={vi.fn().mockResolvedValue([MIC])} install={install} />);
    await userEvent.click(await screen.findByTestId('pack-mic-get'));
    expect(await screen.findByText(/did not install/i)).toBeInTheDocument();
    expect(screen.getByTestId('pack-mic-get')).toBeInTheDocument();
  });
});

describe('the offer at the moment of doubt', () => {
  it('offers the pack with its price where the feature was chosen', async () => {
    render(<PackOffer id="voice" lead="The avatar can speak with the Speaking pack." load={vi.fn().mockResolvedValue([VOICE])} />);
    expect(await screen.findByTestId('pack-offer-voice')).toBeInTheDocument();
    expect(screen.getByTestId('pack-voice-get')).toHaveTextContent('290 MB');
  });

  it('is silent when the pack is already here, or the price cannot be read', async () => {
    const { rerender } = render(
      <PackOffer id="voice" lead="x" load={vi.fn().mockResolvedValue([{ ...VOICE, installed: true }])} />,
    );
    await waitFor(() => expect(screen.queryByTestId('pack-offer-voice')).not.toBeInTheDocument());
    rerender(<PackOffer id="voice" lead="x" load={vi.fn().mockRejectedValue(new Error('offline'))} />);
    await waitFor(() => expect(screen.queryByTestId('pack-offer-voice')).not.toBeInTheDocument());
  });
});
