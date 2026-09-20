/**
 * The model is warmed when the person returns after a real pause — once.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { IDLE_BEFORE_WARM_MS, installWarmOnReturn } from './warmOnReturn';
import { useChatStore } from '@/stores/chatStore';

function harness(start = 1_000_000) {
  let now = start;
  const posts: string[] = [];
  let resolve: () => void = () => {};
  const post = vi.fn((path: string) => {
    posts.push(path);
    return new Promise<void>((r) => {
      resolve = r;
    });
  });
  const teardown = installWarmOnReturn({ now: () => now }, post);
  return {
    posts,
    advance: (ms: number) => {
      now += ms;
    },
    focus: () => window.dispatchEvent(new Event('focus')),
    settle: async () => {
      resolve();
      await Promise.resolve();
      await Promise.resolve();
    },
    teardown,
  };
}

describe('warm on return', () => {
  let h: ReturnType<typeof harness>;

  beforeEach(() => {
    useChatStore.setState({ isStreaming: false });
    h = harness();
  });

  afterEach(() => h.teardown());

  it('does nothing on a quick alt-tab', () => {
    h.advance(5 * 60 * 1000);
    h.focus();
    expect(h.posts).toEqual([]);
  });

  it('asks once after a long pause, and not again on the next focus', async () => {
    h.advance(IDLE_BEFORE_WARM_MS + 1);
    h.focus();
    h.focus();
    expect(h.posts).toEqual(['/models/warm']);
    await h.settle();
    h.focus();
    expect(h.posts).toEqual(['/models/warm']);
  });

  it('counts a reply as activity, so the pause is measured from it', () => {
    h.advance(IDLE_BEFORE_WARM_MS - 1000);
    useChatStore.setState({ isStreaming: true });
    useChatStore.setState({ isStreaming: false });
    h.advance(2000);
    h.focus();
    expect(h.posts).toEqual([]);
  });

  it('stops listening after teardown', () => {
    h.teardown();
    h.advance(IDLE_BEFORE_WARM_MS + 1);
    h.focus();
    expect(h.posts).toEqual([]);
  });
});
