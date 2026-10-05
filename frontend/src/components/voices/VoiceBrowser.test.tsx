/**
 * @vitest-environment jsdom
 *
 * Choosing a voice from the whole pack.
 *
 * * **A voice that needs an extra is greyed, never hidden, and has no button**
 *   — offering a choice that fails on the first sentence looks broken.
 * * **Picking a voice that is not here fetches it first**, and does not pick it
 *   if the fetch failed — otherwise Settings would name a voice that cannot
 *   speak.
 * * **A grade the author did not give is not shown.**
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const fetchVoiceCatalogue = vi.fn();
const downloadVoice = vi.fn();

vi.mock('@/services/characterClient', () => ({
  fetchVoiceCatalogue: () => fetchVoiceCatalogue(),
  downloadVoice: (id: string) => downloadVoice(id),
}));

import VoiceBrowser from './VoiceBrowser';

function voice(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'bf_emma',
    name: 'Emma',
    language: 'British English',
    languageCode: 'b',
    gender: 'female',
    grade: 'B-',
    sizeBytes: 523000,
    installed: false,
    requires: null,
    isDefault: false,
    ...over,
  };
}

const catalogue = (voices: unknown[]) => ({ generated: '2026-10-04', voices });

beforeEach(() => {
  fetchVoiceCatalogue.mockReset().mockResolvedValue(catalogue([voice()]));
  downloadVoice.mockReset().mockResolvedValue(undefined);
});

afterEach(() => cleanup());

const user = () => userEvent.setup();

describe('what each voice offers', () => {
  it('prices a voice that is not here on its button', async () => {
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    expect(await screen.findByTestId('choose-bf_emma')).toHaveTextContent('Download 523 kB');
  });

  it('says "Use" for a voice that is already here', async () => {
    fetchVoiceCatalogue.mockResolvedValue(catalogue([voice({ installed: true })]));
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    expect(await screen.findByTestId('choose-bf_emma')).toHaveTextContent('Use');
  });

  it('greys a voice that needs an extra, names what, and offers no button', async () => {
    fetchVoiceCatalogue.mockResolvedValue(
      catalogue([voice({ id: 'jf_alpha', name: 'Alpha', language: 'Japanese', requires: 'misaki[ja]' })]),
    );
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    expect(await screen.findByTestId('needs-jf_alpha')).toHaveTextContent('needs misaki[ja]');
    expect(screen.queryByTestId('choose-jf_alpha')).toBeNull();
  });

  it('shows the grade when the author gave one and nothing when he did not', async () => {
    fetchVoiceCatalogue.mockResolvedValue(
      catalogue([voice(), voice({ id: 'ef_dora', name: 'Dora', language: 'Spanish', grade: null })]),
    );
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    expect(await screen.findByTestId('voice-bf_emma')).toHaveTextContent('grade B-');
    expect(screen.getByTestId('voice-ef_dora')).not.toHaveTextContent('grade');
  });

  it('marks the speaking voice, falling back to the default when none is chosen', async () => {
    fetchVoiceCatalogue.mockResolvedValue(
      catalogue([voice({ id: 'am_michael', name: 'Michael', isDefault: true, installed: true })]),
    );
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    expect(await screen.findByTestId('voice-am_michael')).toHaveTextContent('speaking');
  });
});

describe('choosing', () => {
  it('fetches a voice that is not here, then picks it', async () => {
    const onSelect = vi.fn();
    render(<VoiceBrowser selected="" onSelect={onSelect} />);
    await user().click(await screen.findByTestId('choose-bf_emma'));
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('bf_emma'));
    expect(downloadVoice).toHaveBeenCalledWith('bf_emma');
  });

  it('does not pick a voice whose download failed, and says nothing changed', async () => {
    downloadVoice.mockRejectedValue(new Error('Zaram could not fetch that voice.'));
    const onSelect = vi.fn();
    render(<VoiceBrowser selected="" onSelect={onSelect} />);
    await user().click(await screen.findByTestId('choose-bf_emma'));
    expect(await screen.findByTestId('voice-browser-error')).toHaveTextContent('Nothing was changed');
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('picks an installed voice without downloading anything', async () => {
    fetchVoiceCatalogue.mockResolvedValue(catalogue([voice({ installed: true })]));
    const onSelect = vi.fn();
    render(<VoiceBrowser selected="" onSelect={onSelect} />);
    await user().click(await screen.findByTestId('choose-bf_emma'));
    expect(onSelect).toHaveBeenCalledWith('bf_emma');
    expect(downloadVoice).not.toHaveBeenCalled();
  });
});

describe('searching', () => {
  it('finds by language', async () => {
    fetchVoiceCatalogue.mockResolvedValue(
      catalogue([voice(), voice({ id: 'ff_siwis', name: 'Siwis', language: 'French' })]),
    );
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    await user().type(await screen.findByTestId('voice-search'), 'french');
    expect(screen.queryByTestId('voice-bf_emma')).toBeNull();
    expect(screen.getByTestId('voice-ff_siwis')).toBeInTheDocument();
  });
});

it('says so when the list cannot be read', async () => {
  fetchVoiceCatalogue.mockResolvedValue({ generated: null, voices: [] });
  render(<VoiceBrowser selected="" onSelect={() => {}} />);
  expect(await screen.findByTestId('no-voices')).toBeInTheDocument();
});
