/**
 * The orb must not report a capability as an activity.
 *
 * Connecting a cloud provider used to light the orb amber — the colour this
 * product uses for a warning — and leave it lit, while every answer was still
 * being generated on the machine. The words had already been split into
 * "Cloud enabled" and "Local · can send" by an earlier fix; both still
 * returned `tone: 'cloud'`, so the half a user reads at a glance was never
 * corrected.
 *
 * These tests pin the distinction rather than the wording, because the wording
 * will change and the distinction must not: **colour follows what happened,
 * words carry what is possible.**
 */
import { describe, expect, it } from 'vitest';

import { describeSystem, useSystemStore, type RoutingState } from './systemStore';

const online = { backendOnline: true, activity: 'idle' as const };

const routing = (over: Partial<RoutingState> = {}): RoutingState => ({
  mode: 'local',
  providers: [],
  webSearch: 'unknown',
  canLeaveDevice: false,
  ...over,
});

const CLOUD_PROVIDER = { id: 'openrouter', locality: 'cloud' };

describe('a connected cloud provider is not an egress', () => {
  it('does not raise the cloud tone merely because one is connected', () => {
    const { tone } = describeSystem({
      ...online,
      routing: routing({ providers: [CLOUD_PROVIDER] }),
    });
    expect(tone).not.toBe('cloud');
  });

  it('still says so in words, because a capability is worth stating', () => {
    const { label, detail } = describeSystem({
      ...online,
      routing: routing({ providers: [CLOUD_PROVIDER] }),
    });
    expect(`${label} ${detail}`.toLowerCase()).toContain('cloud');
  });

  it('does not raise the cloud tone because one search host is allowed', () => {
    const { tone } = describeSystem({
      ...online,
      routing: routing({ canLeaveDevice: true }),
    });
    expect(tone).not.toBe('cloud');
  });
});

describe('an answer that actually came from cloud does raise it', () => {
  it('reports the cloud tone once a cloud model has answered', () => {
    const { tone } = describeSystem({
      ...online,
      routing: routing({ providers: [CLOUD_PROVIDER] }),
      cloudAnsweredAt: Date.now(),
    });
    expect(tone).toBe('cloud');
  });

  it('points the user at Activity, where the bytes are recorded', () => {
    const { detail } = describeSystem({
      ...online,
      routing: routing(),
      cloudAnsweredAt: Date.now(),
    });
    expect(detail).toContain('Activity');
  });

  it('outranks the capability line, so the stronger claim wins', () => {
    const { label } = describeSystem({
      ...online,
      routing: routing({ providers: [CLOUD_PROVIDER], canLeaveDevice: true }),
      cloudAnsweredAt: Date.now(),
    });
    expect(label).toBe('Cloud used');
  });
});

describe('the quiet case stays quiet', () => {
  it('is local only with nothing connected and nothing sent', () => {
    const { label, tone } = describeSystem({ ...online, routing: routing() });
    expect(label).toBe('Local only');
    expect(tone).toBe('local');
  });

  it('an omitted cloudAnsweredAt understates rather than invents', () => {
    // A caller that forgets the field must not manufacture an egress claim.
    // Understating is recoverable; a false "your data left" on the one
    // indicator built to be trusted is not.
    const { tone } = describeSystem({
      ...online,
      routing: routing({ providers: [CLOUD_PROVIDER] }),
    });
    expect(tone).toBe('local');
  });
});

describe('offline and busy still win over everything', () => {
  it('reports offline even with a cloud answer behind it', () => {
    const { tone } = describeSystem({
      backendOnline: false,
      activity: 'idle',
      routing: routing(),
      cloudAnsweredAt: Date.now(),
    });
    expect(tone).toBe('offline');
  });

  it('reports thinking while a reply is in flight', () => {
    const { label } = describeSystem({
      backendOnline: true,
      activity: 'thinking',
      routing: routing(),
      cloudAnsweredAt: Date.now(),
    });
    expect(label).toBe('Thinking');
  });
});

describe('an oversized model is not an ordinary cold start', () => {
  /**
   * `swap_preflight` grades a model larger than the whole resident budget as
   * `oversized` — a hardware fact no setting will change — and the backend has
   * been sending that verdict all along. `chatClient` dropped it as an
   * unrecognised kind, so the user got silence and then a read timeout.
   */
  it('says why this wait will not pass, naming the model', () => {
    const { detail } = describeSystem({
      backendOnline: true,
      routing: routing(),
      activity: 'warming',
      oversizedModel: 'gemma4:26b-a4b-it-q4_K_M',
    });

    expect(detail).toContain('gemma4:26b-a4b-it-q4_K_M');
    expect(detail).not.toContain('first reply of a session');
  });

  it('an ordinary cold start keeps the sentence it had', () => {
    const { detail } = describeSystem({
      backendOnline: true,
      routing: routing(),
      activity: 'warming',
    });

    expect(detail).toContain('first reply of a session');
  });

  it('the name cannot outlive the state that explains it', () => {
    const store = useSystemStore.getState();
    store.beginOversizedLoad('gemma4:26b-a4b-it-q4_K_M');
    expect(useSystemStore.getState().oversizedModel).toBe('gemma4:26b-a4b-it-q4_K_M');

    useSystemStore.getState().setActivity('idle');
    expect(useSystemStore.getState().oversizedModel).toBeNull();
  });
});
