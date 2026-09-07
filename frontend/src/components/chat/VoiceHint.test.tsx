/**
 * When "Press Shift Space to talk" may be on screen, and when it is a lie.
 *
 * The line moved here from the landing on 7 September 2026. The landing carries
 * one instruction — a second beside it asks somebody to choose between two ways
 * in before they have done anything — and the gesture it names only works on
 * this surface anyway.
 *
 * The conditions are the content of this file, because each one is a way for a
 * first-run hint to be wrong: naming a keystroke that does nothing, telling
 * somebody how to start what they have started, and lingering after the thing
 * it was an instruction for.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import VoiceHint from './VoiceHint';
import { useChatStore } from '@/stores/chatStore';
import { useMicStore } from '@/stores/micStore';

function mic(over: { unavailableReason?: string | null; status?: string } = {}) {
  const reason = over.unavailableReason ?? null;
  useMicStore.setState({
    unavailableReason: reason,
    status: over.status ?? 'idle',
    // Availability is asked for on mount; the answer is what the test controls.
    checkAvailability: async () => {
      useMicStore.setState({ unavailableReason: reason } as never);
    },
  } as never);
}

beforeEach(() => {
  mic();
  useChatStore.setState({ messages: [], streamingText: '' } as never);
});
afterEach(cleanup);

describe('the voice hint', () => {
  it('offers the chord in an empty conversation', async () => {
    render(<VoiceHint />);
    expect(await screen.findByText(/shift\s+space/i)).toBeInTheDocument();
  });

  it('prints the chord the registry actually fires on', async () => {
    // Read from `chordTokens` rather than typed into the component. This
    // registry carries two comments recording occasions when the interface
    // advertised a chord nothing answered to.
    const { REGISTRY, chordTokens, detectPlatform } = await import(
      '@/runtime/shortcuts/registry'
    );
    const voice = REGISTRY.find((s) => s.id === 'voice')!;

    render(<VoiceHint />);

    expect(
      await screen.findByText(new RegExp(chordTokens(voice, detectPlatform()), 'i')),
    ).toBeInTheDocument();
  });

  it('says nothing once something has been said', () => {
    // An instruction to start, so it goes the moment the thing has started —
    // the same rule that takes the landing's line away once the orb is clicked.
    useChatStore.setState({ messages: [{ id: 'm1' }] } as never);
    render(<VoiceHint />);
    expect(screen.queryByText(/shift\s+space/i)).not.toBeInTheDocument();
  });

  it('says nothing when Zaram cannot listen', () => {
    // An instruction to press a key that does nothing is an invented value on
    // the first line a new user reads. Naming the missing extra and its 81 MB
    // belongs on the microphone button, where somebody is already asking about
    // voice.
    mic({ unavailableReason: 'Listening needs the mic extra: pip install zaram[mic] (81 MB).' });
    render(<VoiceHint />);

    expect(screen.queryByText(/shift\s+space/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/81 MB/)).not.toBeInTheDocument();
  });

  it('says nothing while the microphone is already open', () => {
    // Telling somebody how to start something they have started reads as the
    // product not knowing what it is doing.
    mic({ status: 'recording' });
    render(<VoiceHint />);

    expect(screen.queryByText(/shift\s+space/i)).not.toBeInTheDocument();
  });
});
