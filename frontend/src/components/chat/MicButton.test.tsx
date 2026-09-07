/**
 * Two gestures on one control, and the ways that goes wrong.
 *
 * The component's own note explains why holding was refused here for weeks and
 * what changed. What this file asserts is the part that reasoning does not
 * cover: that adding the second gesture did not quietly take the first one
 * away, that a hold is not also read as a click, and that the mode the hold
 * opens is reachable and describable without a pointer.
 *
 * Everything below drives the real component against a stubbed store. The
 * store's own machinery — the detector, the level loop, the transcription — is
 * covered in `lib/voiceActivity.test.ts`; opening an `AudioContext` in jsdom
 * would assert the mock rather than the behaviour.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import MicButton from './MicButton';
import { useMicStore } from '@/stores/micStore';
import { useSpeechStore } from '@/stores/speechStore';

const actions = {
  start: vi.fn(async () => undefined),
  stop: vi.fn(async () => 'what was heard'),
  cancel: vi.fn(),
  startLatched: vi.fn(async () => undefined),
  stopLatched: vi.fn(),
  checkAvailability: vi.fn(async () => undefined),
};

/** Put the store in one state and leave the actions as spies. */
function stubStore(over: Partial<ReturnType<typeof useMicStore.getState>> = {}) {
  useMicStore.setState({
    status: 'idle',
    mode: 'push',
    level: 0,
    hearingVoice: false,
    unavailableReason: null,
    error: null,
    figureNotice: null,
    ...actions,
    ...over,
  } as ReturnType<typeof useMicStore.getState>);
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  Object.values(actions).forEach((fn) => fn.mockClear());
  stubStore();
  useSpeechStore.setState({ audio: null } as never);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const user = () => userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

describe('a click still does what it always did', () => {
  it('starts one recording', async () => {
    render(<MicButton onTranscript={vi.fn()} />);

    await user().click(screen.getByRole('button'));

    expect(actions.start).toHaveBeenCalledTimes(1);
    expect(actions.startLatched).not.toHaveBeenCalled();
  });

  it('stops and hands the transcript to the caller', async () => {
    const onTranscript = vi.fn();
    stubStore({ status: 'recording' });
    render(<MicButton onTranscript={onTranscript} />);

    await user().click(screen.getByRole('button'));

    expect(actions.stop).toHaveBeenCalledTimes(1);
    expect(onTranscript).toHaveBeenCalledWith('what was heard');
  });

  it('stops Zaram talking before it opens the microphone', async () => {
    // A correctness requirement rather than a courtesy: the microphone would
    // otherwise record Zaram's own voice from the speakers and transcribe it
    // back as if the user had said it.
    const bargeIn = vi.fn();
    useSpeechStore.setState({ bargeIn } as never);
    render(<MicButton onTranscript={vi.fn()} />);

    await user().click(screen.getByRole('button'));

    expect(bargeIn).toHaveBeenCalled();
  });
});

describe('holding it opens a conversation', () => {
  it('latches once the press has lasted', async () => {
    render(<MicButton onTranscript={vi.fn()} />);
    const button = screen.getByRole('button');

    await user().pointer({ keys: '[MouseLeft>]', target: button });
    vi.advanceTimersByTime(600);

    expect(actions.startLatched).toHaveBeenCalledTimes(1);
    expect(actions.start).not.toHaveBeenCalled();
  });

  it('does not also toggle when the finger comes up', async () => {
    // The failure this guards is silent and total: the press latches, the
    // release reads as a click, the click stops it, and the feature appears
    // never to have worked.
    render(<MicButton onTranscript={vi.fn()} />);
    const button = screen.getByRole('button');

    await user().pointer({ keys: '[MouseLeft>]', target: button });
    vi.advanceTimersByTime(600);
    await user().pointer({ keys: '[/MouseLeft]', target: button });

    expect(actions.stopLatched).not.toHaveBeenCalled();
    expect(actions.start).not.toHaveBeenCalled();
  });

  it('is an ordinary click if released early', async () => {
    render(<MicButton onTranscript={vi.fn()} />);

    await user().click(screen.getByRole('button'));

    expect(actions.startLatched).not.toHaveBeenCalled();
    expect(actions.start).toHaveBeenCalledTimes(1);
  });

  it('does not latch if the pointer leaves before the hold completes', async () => {
    render(<MicButton onTranscript={vi.fn()} />);
    const button = screen.getByRole('button');

    await user().pointer({ keys: '[MouseLeft>]', target: button });
    fireEvent.pointerLeave(button);
    vi.advanceTimersByTime(600);

    expect(actions.startLatched).not.toHaveBeenCalled();
  });

  it('leaves the mode on a plain click', async () => {
    stubStore({ status: 'recording', mode: 'latched' });
    render(<MicButton onTranscript={vi.fn()} />);

    await user().click(screen.getByRole('button'));

    expect(actions.stopLatched).toHaveBeenCalledTimes(1);
  });
});

describe('without a pointer', () => {
  it('reaches the same mode with a modifier', async () => {
    // A modifier held while Enter is pressed travels to the click event, so
    // this is the keyboard's route in. Without it the mode is pointer-only,
    // which is the objection this component's note used to answer by refusing
    // the gesture altogether.
    render(<MicButton onTranscript={vi.fn()} />);

    // One session throughout: a modifier is state held by the session, so a
    // fresh `user()` for the click would drop it and quietly test a plain
    // click instead.
    const session = user();
    await session.keyboard('{Alt>}');
    await session.click(screen.getByRole('button'));
    await session.keyboard('{/Alt}');

    expect(actions.startLatched).toHaveBeenCalledTimes(1);
    expect(actions.start).not.toHaveBeenCalled();
  });

  it('names the second gesture rather than leaving it to be discovered', () => {
    render(<MicButton onTranscript={vi.fn()} />);

    expect(screen.getByRole('button')).toHaveAccessibleName(/hold down for a long conversation/i);
  });

  it('says it is listening once latched, and that a click ends it', () => {
    stubStore({ status: 'recording', mode: 'latched' });
    render(<MicButton onTranscript={vi.fn()} />);

    const button = screen.getByRole('button');
    expect(button).toHaveAccessibleName(/listening/i);
    expect(button).toHaveAccessibleName(/click to stop/i);
    // The icon changing announces nothing on its own.
    expect(button).toHaveAttribute('aria-pressed', 'true');
  });

  it('says when it is actually hearing something', () => {
    // The difference between a microphone that is on and one that is working.
    stubStore({ status: 'recording', mode: 'latched', hearingVoice: true, level: 0.1 });
    render(<MicButton onTranscript={vi.fn()} />);

    expect(screen.getByRole('button')).toHaveAccessibleName(/hearing you/i);
  });
});

describe('when Zaram cannot listen', () => {
  it('is disabled with the backend’s own reason', () => {
    stubStore({ unavailableReason: 'Listening needs the mic extra: pip install zaram[mic] (81 MB).' });
    render(<MicButton onTranscript={vi.fn()} />);

    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleName(/81 MB/);
  });

  it('cannot be latched by holding it either', async () => {
    stubStore({ unavailableReason: 'nope' });
    render(<MicButton onTranscript={vi.fn()} />);

    await user().pointer({ keys: '[MouseLeft>]', target: screen.getByRole('button') });
    vi.advanceTimersByTime(600);

    expect(actions.startLatched).not.toHaveBeenCalled();
  });
});
