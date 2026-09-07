/**
 * The landing's one line.
 *
 * It had two for part of 7 September 2026 — a voice hint under "Click Orb to
 * Chat" — and the second moved to the conversation at the maintainer's
 * direction. The reasoning is worth keeping, because it is a rule rather than a
 * preference: **the landing carries one instruction.** A second beside it asks
 * somebody to choose between two ways in before they have done anything, which
 * is rule 7h in miniature — and the gesture it named only works on the surface
 * it moved to. `chat/VoiceHint.tsx` holds it now, along with the tests for when
 * it may be shown at all.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

import LandingHint from './LandingHint';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useEmbodimentStore } from '@/stores/embodimentStore';
import { useSystemStore } from '@/stores/systemStore';

beforeEach(() => {
  // The component owns the /health poll, which is not what is under test here.
  useSystemStore.setState({ startPolling: () => () => undefined } as never);
  useChatModeStore.setState({ chatView: 'landing' } as never);
  useEmbodimentStore.setState({ renderer: 'orb' } as never);
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

  it('names the avatar when that is what is on screen', () => {
    // The hint names a target, and the target is a choice the user already
    // made. Saying "Orb" to somebody looking at a character names a thing that
    // is not there, on the first line they read.
    useEmbodimentStore.setState({ renderer: 'avatar' } as never);
    render(<LandingHint isLanding />);

    expect(screen.getByText(/click avatar to chat/i)).toBeInTheDocument();
    expect(screen.queryByText(/click orb/i)).not.toBeInTheDocument();
  });

  it('goes once the conversation is open', () => {
    // It is an instruction to do a thing, so it has no reason to persist once
    // the thing is done.
    useChatModeStore.setState({ chatView: 'chat' } as never);
    render(<LandingHint isLanding />);
    expect(screen.queryByText(/click orb to chat/i)).not.toBeInTheDocument();
  });
});

