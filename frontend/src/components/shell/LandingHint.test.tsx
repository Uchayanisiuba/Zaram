/**
 * The landing's two lines, and when the second one is a lie.
 *
 * *"Click Orb to Chat"* is unconditional — the orb is always there. The voice
 * line is not, and that is the whole content of this file: `CLAUDE.md` requires
 * that **disabled capabilities are visible, not silent** and, in the same
 * breath, that Zaram **never renders invented values**. Those pull in opposite
 * directions on a first-run hint, and the resolution is that an *instruction to
 * do a thing* is only honest when the thing exists.
 *
 * Advertising "Shift Space to talk" on a machine without `zaram[mic]` puts a
 * keystroke that does nothing on the first line a new user reads. The place to
 * name a missing extra, its reason and its 81 MB is the microphone button and
 * Settings, where somebody is already asking about voice — not the landing,
 * where nobody has asked anything yet.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import LandingHint from './LandingHint';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useMicStore } from '@/stores/micStore';
import { useSystemStore } from '@/stores/systemStore';

/** Availability is asked for on mount; the answer is what the test controls. */
function micAnswers(reason: string | null) {
  useMicStore.setState({
    unavailableReason: reason,
    checkAvailability: async () => {
      useMicStore.setState({ unavailableReason: reason });
    },
  } as never);
}

beforeEach(() => {
  // The component owns the /health poll, which is not what is under test here.
  useSystemStore.setState({ startPolling: () => () => undefined } as never);
  useChatModeStore.setState({ chatView: 'landing' } as never);
  micAnswers(null);
});

afterEach(cleanup);

describe('the way in', () => {
  it('names the orb', () => {
    render(<LandingHint isLanding />);
    expect(screen.getByText(/click orb to chat/i)).toBeInTheDocument();
  });

  it('says nothing on another surface', () => {
    render(<LandingHint isLanding={false} />);
    expect(screen.queryByText(/click orb to chat/i)).not.toBeInTheDocument();
  });

  it('goes once the conversation is open', () => {
    // It is an instruction to do a thing, so it has no reason to persist once
    // the thing is done.
    useChatModeStore.setState({ chatView: 'chat' } as never);
    render(<LandingHint isLanding />);
    expect(screen.queryByText(/click orb to chat/i)).not.toBeInTheDocument();
  });
});

describe('the voice line', () => {
  it('offers the chord when Zaram can listen', async () => {
    render(<LandingHint isLanding />);
    expect(await screen.findByText(/shift\s+space/i)).toBeInTheDocument();
  });

  it('prints the chord the registry actually fires on', async () => {
    // Read from `chordTokens` rather than typed into the component, so the
    // line and the matcher cannot drift — the failure this registry has already
    // recorded twice, where the interface advertised a chord nothing answered
    // to.
    const { REGISTRY, chordTokens, detectPlatform } = await import('@/runtime/shortcuts/registry');
    const voice = REGISTRY.find((s) => s.id === 'voice')!;

    render(<LandingHint isLanding />);

    expect(
      await screen.findByText(new RegExp(chordTokens(voice, detectPlatform()), 'i')),
    ).toBeInTheDocument();
  });

  it('says nothing when Zaram cannot listen', async () => {
    // Not a quieter version of the offer, and not the reason either. A landing
    // is not where somebody is asking about voice.
    micAnswers('Listening needs the mic extra: pip install zaram[mic] (81 MB, one time).');

    render(<LandingHint isLanding />);

    expect(screen.queryByText(/shift\s+space/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/81 MB/)).not.toBeInTheDocument();
    // And the way in is untouched — a missing extra must not cost the user the
    // line that tells them how to start at all.
    expect(screen.getByText(/click orb to chat/i)).toBeInTheDocument();
  });
});
