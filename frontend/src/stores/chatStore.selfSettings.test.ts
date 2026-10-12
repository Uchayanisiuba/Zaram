/**
 * @vitest-environment jsdom
 *
 * "Switch to the avatar", "open Settings", said to Zaram.
 *
 * 10 October 2026, asked for by the maintainer: people should be able to change
 * Zaram from the conversation. The indicator and the open place belong to the
 * window, so Zaram's own settings tool returns an `apply` instruction and the
 * window carries it out. What has to hold:
 *
 * * **It happens when the call ran**, and only then — a refusal or a card still
 *   waiting changes nothing.
 * * **Only the keys the window knows**, with values checked; anything else in
 *   `apply` is dropped at the parser.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { parseApply, type ChatEvent, type ToolApply } from '@/services/chatClient';

const streamChat = vi.fn();

vi.mock('@/services/chatClient', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/chatClient')>()),
  streamChat: (...args: unknown[]) => streamChat(...args),
}));

import { useChatStore } from '@/stores/chatStore';
import { useEmbodimentStore } from '@/stores/embodimentStore';
import { useSystemStore } from '@/stores/systemStore';

function finished(events: ChatEvent[]) {
  return () =>
    (async function* () {
      for (const e of events) yield e;
    })();
}

function call(verdict: string, apply: ToolApply | undefined): ChatEvent {
  return {
    type: 'tool_call',
    server: 'zaram-self',
    tool: 'set_indicator',
    verdict,
    reason: '',
    target: '',
    output: '',
    diff: '',
    commit: '',
    image: '',
    appUrl: '',
    ...(apply ? { apply } : {}),
  } as ChatEvent;
}

beforeEach(() => {
  streamChat.mockReset();
  useSystemStore.setState({ activity: 'idle', swappingTo: null, oversizedModel: null });
  useEmbodimentStore.setState({ renderer: 'orb' });
  useChatStore.setState({ messages: [], isStreaming: false, streamingText: '', requestedPlace: null });
});

describe('changing the window from the conversation', () => {
  it('switches the indicator when the call ran', async () => {
    streamChat.mockImplementationOnce(finished([call('allow', { renderer: 'avatar' })]));
    await useChatStore.getState().send('switch to the avatar');
    expect(useEmbodimentStore.getState().renderer).toBe('avatar');
  });

  it('asks the conversation view to open a place', async () => {
    streamChat.mockImplementationOnce(finished([call('allow', { open: 'settings' })]));
    await useChatStore.getState().send('open settings');
    expect(useChatStore.getState().requestedPlace).toBe('settings');
    useChatStore.getState().clearRequestedPlace();
    expect(useChatStore.getState().requestedPlace).toBeNull();
  });

  it('changes nothing while the card is still waiting', async () => {
    streamChat.mockImplementationOnce(finished([call('confirm', { renderer: 'avatar', open: 'memory' })]));
    await useChatStore.getState().send('switch to the avatar');
    expect(useEmbodimentStore.getState().renderer).toBe('orb');
    expect(useChatStore.getState().requestedPlace).toBeNull();
  });
});

describe('parseApply', () => {
  it('keeps only known keys with known values', () => {
    expect(parseApply({ renderer: 'avatar', open: 'settings' })).toEqual({ renderer: 'avatar', open: 'settings' });
    expect(parseApply({ renderer: 'hologram', open: 'canvas', run: 'rm -rf' })).toBeUndefined();
    expect(parseApply({ open: 'activity', theme: 'dark' })).toEqual({ open: 'activity' });
    expect(parseApply('avatar')).toBeUndefined();
    expect(parseApply(null)).toBeUndefined();
  });
});
