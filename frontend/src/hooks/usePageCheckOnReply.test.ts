/**
 * @vitest-environment jsdom
 */
import { describe, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { usePageCheckOnReply } from './usePageCheckOnReply';

type Turn = { role: string; text: string };
const user = (text: string): Turn => ({ role: 'user', text });
const bot = (text: string): Turn => ({ role: 'assistant', text });

function mount(initial: { messages: Turn[]; streaming: boolean }) {
  const check = vi.fn();
  const hook = renderHook((p: { messages: Turn[]; streaming: boolean }) => usePageCheckOnReply(p.messages, p.streaming, check), {
    initialProps: initial,
  });
  return { check, ...hook };
}

describe('when a page check starts', () => {
  it('when a reply finishes streaming, with the reply and the question that asked for it', () => {
    const { check, rerender } = mount({ messages: [], streaming: false });
    rerender({ messages: [user('make a game')], streaming: true });
    rerender({ messages: [user('make a game'), bot('here it is')], streaming: false });
    expect(check).toHaveBeenCalledTimes(1);
    expect(check).toHaveBeenCalledWith('here it is', 'make a game');
  });

  it('even when the reply is committed a render after streaming stops', () => {
    const { check, rerender } = mount({ messages: [], streaming: false });
    rerender({ messages: [user('q')], streaming: true });
    rerender({ messages: [user('q')], streaming: false });
    expect(check).not.toHaveBeenCalled();
    rerender({ messages: [user('q'), bot('a')], streaming: false });
    expect(check).toHaveBeenCalledWith('a', 'q');
  });

  it('not for a conversation that was opened, however many pages are in it', () => {
    const { check, rerender } = mount({ messages: [], streaming: false });
    rerender({ messages: [user('q'), bot('```html\n<p>x</p>\n```')], streaming: false });
    expect(check).not.toHaveBeenCalled();
  });

  it('once, however often the list changes afterwards', () => {
    const { check, rerender } = mount({ messages: [], streaming: false });
    rerender({ messages: [user('q')], streaming: true });
    const done = [user('q'), bot('a')];
    rerender({ messages: done, streaming: false });
    rerender({ messages: [...done], streaming: false });
    expect(check).toHaveBeenCalledTimes(1);
  });

  it('not for a stream that ended with nothing to show, nor for the message that arrives later', () => {
    const { check, rerender } = mount({ messages: [], streaming: false });
    rerender({ messages: [user('q')], streaming: true });
    rerender({ messages: [user('q')], streaming: false });
    // Another conversation is opened afterwards: its history is not a reply.
    rerender({ messages: [user('x'), bot('old page')], streaming: false });
    expect(check).not.toHaveBeenCalled();
  });

  it('for a reply that follows the person sending another message', () => {
    const { check, rerender } = mount({ messages: [user('one'), bot('first')], streaming: false });
    rerender({ messages: [user('one'), bot('first'), user('two')], streaming: true });
    rerender({ messages: [user('one'), bot('first'), user('two'), bot('second')], streaming: false });
    expect(check).toHaveBeenCalledTimes(1);
    expect(check).toHaveBeenCalledWith('second', 'two');
  });
});
