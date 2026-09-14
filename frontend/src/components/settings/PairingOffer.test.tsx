/**
 * The offer asks nothing until pressed, shows each pick with its reason,
 * assigns exactly what was shown, and says what staying local costs.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import PairingOffer from './PairingOffer';

const fetchPairing = vi.fn();
const applyPairing = vi.fn();
vi.mock('@/services/settingsClient', () => ({
  fetchPairing: (id: string) => fetchPairing(id),
  applyPairing: (id: string, picks: unknown) => applyPairing(id, picks),
}));

afterEach(cleanup);
beforeEach(() => {
  fetchPairing.mockReset();
  applyPairing.mockReset();
});

const pairing = {
  providerId: 'nvidia_nim',
  displayName: 'NVIDIA NIM',
  generated: '2026-09-14',
  seen: 40,
  picks: {
    chat: { model: 'nvidia/nemotron-3.5-lightning-30b-a3b', why: 'fast' },
    code: { model: 'qwen/qwen3-coder-480b-a35b-instruct', why: 'finishes long chains' },
  },
};

describe('the pairing offer', () => {
  it('asks the provider nothing until the person presses See picks', async () => {
    render(<PairingOffer providerId="nvidia_nim" displayName="NVIDIA NIM" />);
    expect(fetchPairing).not.toHaveBeenCalled();
    expect(screen.getByTestId('pairing-see')).toBeInTheDocument();
  });

  it('shows each pick with its reason, the deal, and that local is free', async () => {
    fetchPairing.mockResolvedValue(pairing);
    const user = userEvent.setup();
    render(<PairingOffer providerId="nvidia_nim" displayName="NVIDIA NIM" />);
    await user.click(screen.getByTestId('pairing-see'));

    const picks = await screen.findByTestId('pairing-picks');
    expect(picks).toHaveTextContent('Coding chains');
    expect(picks).toHaveTextContent('qwen/qwen3-coder-480b-a35b-instruct');
    expect(picks).toHaveTextContent('finishes long chains');
    expect(screen.getByTestId('pairing-offer')).toHaveTextContent(/may be trained on/);
    expect(screen.getByTestId('pairing-offer')).toHaveTextContent(/Local is free too/);
    expect(screen.getByTestId('pairing-offer')).toHaveTextContent('list dated 2026-09-14');
  });

  it('assigns exactly what was shown', async () => {
    fetchPairing.mockResolvedValue(pairing);
    applyPairing.mockResolvedValue({ assigned: { chat: 'x', code: 'y', vision: null } });
    const onAssigned = vi.fn();
    const user = userEvent.setup();
    render(<PairingOffer providerId="nvidia_nim" displayName="NVIDIA NIM" onAssigned={onAssigned} />);
    await user.click(screen.getByTestId('pairing-see'));
    await user.click(await screen.findByTestId('pairing-assign'));

    await waitFor(() => expect(applyPairing).toHaveBeenCalledWith('nvidia_nim', pairing.picks));
    expect(onAssigned).toHaveBeenCalledWith({ chat: 'x', code: 'y', vision: null });
    expect(screen.getByTestId('pairing-offer')).toHaveTextContent(/Assigned\./);
  });

  it('says so when the key sees none of the listed models, and invents nothing', async () => {
    fetchPairing.mockResolvedValue({ ...pairing, picks: {}, seen: 3 });
    const user = userEvent.setup();
    render(<PairingOffer providerId="nvidia_nim" displayName="NVIDIA NIM" />);
    await user.click(screen.getByTestId('pairing-see'));
    expect(await screen.findByText(/None of the models on the list/)).toBeInTheDocument();
    expect(screen.queryByTestId('pairing-assign')).toBeNull();
  });
});
