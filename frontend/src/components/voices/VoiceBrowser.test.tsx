/**
 * @vitest-environment jsdom
 *
 * Choosing a voice from the active TTS provider.
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

const fetchActiveVoiceCatalogue = vi.fn();
const downloadVoice = vi.fn();
const fetchTierStatus = vi.fn();
const fetchHardwareProfile = vi.fn();
const cleanupVoiceCache = vi.fn();

vi.mock('@/services/characterClient', () => ({
  fetchActiveVoiceCatalogue: () => fetchActiveVoiceCatalogue(),
  downloadVoice: (id: string) => downloadVoice(id),
  fetchTierStatus: () => fetchTierStatus(),
  fetchHardwareProfile: () => fetchHardwareProfile(),
  cleanupVoiceCache: (keepVoice: string, dryRun: boolean) => cleanupVoiceCache(keepVoice, dryRun),
}));

const speak = vi.fn();
const speech = { error: null as string | null };

vi.mock('@/stores/speechStore', () => ({
  useSpeechStore: {
    getState: () => ({ speak: (text: string, voice: string) => speak(text, voice), error: speech.error }),
  },
}));

import VoiceBrowser from './VoiceBrowser';

function activeVoice(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'bf_emma',
    name: 'Emma',
    language: 'British English',
    languageCode: 'b',
    gender: 'female',
    grade: 'B-',
    provider: 'kokoro',
    available: true,
    ...over,
  };
}

const activeCatalogue = (voices: unknown[]) => ({
  provider: 'kokoro',
  activeTier: 'TIER_4_KOKORO',
  voices,
  providerHealth: 'healthy',
});

const defaultTierStatus = {
  active_tier: 'TIER_4_KOKORO',
  active_provider: 'kokoro',
  auto_tier_enabled: true,
  prefer_local: true,
  tier_status: {
    TIER_4_KOKORO: {
      provider: 'kokoro',
      eligible: true,
      reason: 'all conditions met',
      description: 'Kokoro 82M - Universal fallback',
      requires_cloud: false,
      requires_gpu: false,
    },
  },
};

const defaultHardwareProfile = {
  gpu_vendor: 'unknown',
  gpu_name: 'unknown',
  total_vram_gb: null,
  free_vram_gb: null,
  total_system_ram_gb: null,
  free_system_ram_gb: null,
  cloud_llm_active: false,
  cloud_llm_provider: null,
  local_llm_active: false,
  local_llm_model_id: null,
  local_llm_vram_footprint_gb: null,
  os_name: 'windows',
  arch: 'x64',
};

beforeEach(() => {
  fetchActiveVoiceCatalogue.mockReset().mockResolvedValue(activeCatalogue([activeVoice()]));
  downloadVoice.mockReset().mockResolvedValue(undefined);
  speak.mockReset().mockResolvedValue(undefined);
  speech.error = null;
  fetchTierStatus.mockReset().mockResolvedValue(defaultTierStatus);
  fetchHardwareProfile.mockReset().mockResolvedValue(defaultHardwareProfile);
  cleanupVoiceCache.mockReset().mockResolvedValue({ deleted_count: 0, freed_bytes: 0, freed_mb: 0, kept_count: 0, dry_run: false, errors: [] });
});

afterEach(() => cleanup());

const user = () => userEvent.setup();

describe('what each voice offers', () => {
  it('shows "Use" for an available voice', async () => {
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    expect(await screen.findByTestId('choose-bf_emma')).toHaveTextContent('Use');
  });

  it('greys a voice that is unavailable, names what, and offers no button', async () => {
    fetchActiveVoiceCatalogue.mockResolvedValue(
      activeCatalogue([activeVoice({ id: 'jf_alpha', name: 'Alpha', language: 'Japanese', available: false })]),
    );
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    expect(await screen.findByTestId('unavailable-jf_alpha')).toHaveTextContent('unavailable (kokoro)');
    expect(screen.queryByTestId('choose-jf_alpha')).toBeNull();
  });

  it('shows the grade when the author gave one and nothing when he did not', async () => {
    fetchActiveVoiceCatalogue.mockResolvedValue(
      activeCatalogue([activeVoice(), activeVoice({ id: 'ef_dora', name: 'Dora', language: 'Spanish', grade: null })]),
    );
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    expect(await screen.findByTestId('voice-bf_emma')).toHaveTextContent('grade B-');
    expect(screen.getByTestId('voice-ef_dora')).not.toHaveTextContent('grade');
  });

  it('marks the speaking voice when selected prop matches', async () => {
    fetchActiveVoiceCatalogue.mockResolvedValue(
      activeCatalogue([activeVoice({ id: 'am_michael', name: 'Michael' })]),
    );
    render(<VoiceBrowser selected="am_michael" onSelect={() => {}} />);
    expect(await screen.findByTestId('voice-am_michael')).toHaveTextContent('speaking');
  });
});

describe('choosing', () => {
  it('picks an available voice without downloading', async () => {
    const onSelect = vi.fn();
    render(<VoiceBrowser selected="" onSelect={onSelect} />);
    await user().click(await screen.findByTestId('choose-bf_emma'));
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('bf_emma'));
    expect(downloadVoice).not.toHaveBeenCalled();
  });

});

describe('a voice that is not on this machine yet', () => {
  const missing = (over: Partial<Record<string, unknown>> = {}) =>
    activeVoice({ id: 'af_nicole', name: 'Nicole', installed: false, sizeBytes: 523000, ...over });

  it('offers a download with its price, and neither a test nor a use', async () => {
    fetchActiveVoiceCatalogue.mockResolvedValue(activeCatalogue([missing()]));
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    const button = await screen.findByTestId('download-af_nicole');
    expect(button).toHaveTextContent('Download');
    expect(button).toHaveTextContent('0.5 MB');
    expect(screen.queryByTestId('test-af_nicole')).toBeNull();
    expect(screen.queryByTestId('choose-af_nicole')).toBeNull();
  });

  it('downloads it and nothing else: it is not chosen, so voices can be collected and tried', async () => {
    fetchActiveVoiceCatalogue.mockResolvedValue(activeCatalogue([missing()]));
    const onSelect = vi.fn();
    render(<VoiceBrowser selected="" onSelect={onSelect} />);
    await user().click(await screen.findByTestId('download-af_nicole'));
    await waitFor(() => expect(downloadVoice).toHaveBeenCalledWith('af_nicole'));
    expect(onSelect).not.toHaveBeenCalled();
    // and the list is read again, so the row can say it is here now
    await waitFor(() => expect(fetchActiveVoiceCatalogue.mock.calls.length).toBeGreaterThan(1));
  });

  it('says why when the download is refused, and changes nothing', async () => {
    fetchActiveVoiceCatalogue.mockResolvedValue(activeCatalogue([missing()]));
    downloadVoice.mockRejectedValue(new Error('huggingface.co is not allowed.'));
    const onSelect = vi.fn();
    render(<VoiceBrowser selected="" onSelect={onSelect} />);
    await user().click(await screen.findByTestId('download-af_nicole'));
    expect(await screen.findByTestId('voice-browser-error')).toHaveTextContent('huggingface.co is not allowed.');
    expect(screen.getByTestId('voice-browser-error')).toHaveTextContent('Nothing was changed.');
    expect(onSelect).not.toHaveBeenCalled();
  });
});

describe('trying a voice', () => {
  it('plays a sample in that voice and changes nothing', async () => {
    const onSelect = vi.fn();
    render(<VoiceBrowser selected="" onSelect={onSelect} />);
    await user().click(await screen.findByTestId('test-bf_emma'));
    await waitFor(() => expect(speak).toHaveBeenCalledTimes(1));
    expect(speak.mock.calls[0][1]).toBe('bf_emma');
    expect(String(speak.mock.calls[0][0]).length).toBeGreaterThan(20);
    expect(onSelect).not.toHaveBeenCalled();
    expect(downloadVoice).not.toHaveBeenCalled();
  });

  it('says so when the sample could not be played', async () => {
    speech.error = 'Speech failed (500).';
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    await user().click(await screen.findByTestId('test-bf_emma'));
    expect(await screen.findByTestId('voice-browser-error')).toHaveTextContent('Speech failed (500).');
  });

  it('offers a test beside the voice that is speaking too', async () => {
    fetchActiveVoiceCatalogue.mockResolvedValue(activeCatalogue([activeVoice({ id: 'am_michael', name: 'Michael' })]));
    render(<VoiceBrowser selected="am_michael" onSelect={() => {}} />);
    expect(await screen.findByTestId('test-am_michael')).toBeInTheDocument();
    expect(screen.getByTestId('voice-am_michael')).toHaveTextContent('speaking');
  });
});

describe('the other speech engines', () => {
  it('are named as not built yet, in words and not only on hover', async () => {
    const stub = (provider: string) => ({
      provider,
      eligible: false,
      implemented: false,
      reason: "not built yet: this tier's provider is a stub",
      description: '',
      requires_cloud: false,
      requires_gpu: false,
    });
    fetchTierStatus.mockResolvedValue({
      ...defaultTierStatus,
      tier_status: {
        TIER_1_BREEZE: stub('breeze_tts'),
        TIER_2_CHATTERBOX: stub('chatterbox_turbo'),
        TIER_3_QWEN3: stub('qwen3_tts'),
        ...defaultTierStatus.tier_status,
      },
    });
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    const note = await screen.findByTestId('engines-not-built');
    expect(note).toHaveTextContent('Kokoro is the only speech engine that works today');
    expect(note).toHaveTextContent('Breeze, Chatterbox, Qwen3 are not built yet');
  });

  it('say nothing when there is nothing to say', async () => {
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    await screen.findByTestId('voice-bf_emma');
    expect(screen.queryByTestId('engines-not-built')).toBeNull();
  });
});

describe('what a greyed voice says it needs', () => {
  it('names the language pack', async () => {
    fetchActiveVoiceCatalogue.mockResolvedValue(
      activeCatalogue([
        activeVoice({ id: 'jf_alpha', name: 'Alpha', language: 'Japanese', available: false, requires: 'misaki[ja]' }),
      ]),
    );
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    expect(await screen.findByTestId('unavailable-jf_alpha')).toHaveTextContent('needs misaki[ja]');
  });
});

describe('the voice that speaks by default', () => {
  it('is marked as speaking when nothing has been chosen', async () => {
    fetchActiveVoiceCatalogue.mockResolvedValue(
      activeCatalogue([activeVoice({ id: 'am_michael', name: 'Michael', default: true })]),
    );
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    expect(await screen.findByTestId('voice-am_michael')).toHaveTextContent('speaking');
  });
});

describe('searching', () => {
  it('finds by language', async () => {
    fetchActiveVoiceCatalogue.mockResolvedValue(
      activeCatalogue([activeVoice(), activeVoice({ id: 'ff_siwis', name: 'Siwis', language: 'French' })]),
    );
    render(<VoiceBrowser selected="" onSelect={() => {}} />);
    await user().type(await screen.findByTestId('voice-search'), 'french');
    expect(screen.queryByTestId('voice-bf_emma')).toBeNull();
    expect(screen.getByTestId('voice-ff_siwis')).toBeInTheDocument();
  });
});

it('says so when the list cannot be read', async () => {
  fetchActiveVoiceCatalogue.mockResolvedValue({ provider: null, activeTier: null, voices: [], providerHealth: 'unavailable' });
  render(<VoiceBrowser selected="" onSelect={() => {}} />);
  expect(await screen.findByTestId('no-matching-voices')).toBeInTheDocument();
});