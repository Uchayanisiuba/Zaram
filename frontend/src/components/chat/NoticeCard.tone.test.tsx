/**
 * The amber triangle is spent only where a person is actually at risk.
 *
 * This component's header has argued it since the second case — *"warning the
 * user about their own setting is how an indicator gets trained away, and the
 * amber one has real work to do"* — and the argument kept being lost one kind
 * at a time, because a notice added to the backend after the tone map falls
 * through to the amber default without anyone deciding that it should.
 *
 * Audited on 15 September 2026 after the maintainer asked why a caution mark
 * was on something that endangers nobody. This test is what stops the next
 * kind arriving the same way: a new notice either gets a tone here or fails
 * this file, which makes it a decision rather than a default.
 */
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';

import NoticeCard from './NoticeCard';
import type { ChatNotice } from '../../stores/chatStore';

const AMBER = 'var(--color-amber, #d97706)'; // the token as the component sets it

const notice = (kind: string, action = ''): ChatNotice => ({
  content: 'something happened',
  kind,
  action,
});

function iconColour(kind: string, action = ''): string {
  const { container } = render(
    <NoticeCard notice={notice(kind, action)} onOpen={vi.fn()} onEnableSearch={vi.fn()} />,
  );
  const svg = container.querySelector('svg');
  return svg?.getAttribute('color') ?? svg?.style.color ?? '';
}

describe('which notices are allowed to alarm the reader', () => {
  it.each([
    ['domain', 'answering inside a domain the user chose'],
    ['attachment', 'how much of a file the model saw — usually the good outcome'],
    ['tool_loop', 'the reading allowance was spent'],
    ['memory', 'the window filled and the earliest exchanges dropped'],
    ['untrusted', 'a passage was quoted rather than obeyed — the defence working'],
    ['plan', 'the plan is waiting on a person to press Go'],
    ['tools', 'servers are available for this question'],
    ['step', 'something the model said between steps'],
    ['resident', 'a model swap the user can do nothing about'],
    ['search', 'search is off, and the card carries the switch'],
  ])('%s is neutral — %s', (kind) => {
    expect(iconColour(kind)).not.toBe(AMBER);
  });

  it.each([
    ['ingest', 'a file the user added gave nothing back'],
    ['stuck', 'this would send the question and the files to a cloud model'],
  ])('%s keeps the warning — %s', (kind) => {
    expect(iconColour(kind)).toBe(AMBER);
  });

  it('keeps the warning for a kind nobody has classified', () => {
    // Understating a problem is the worse of the two failures, so an
    // unrecognised kind stays loud — and lands in this file's first list only
    // when somebody decides it should.
    expect(iconColour('something_new_nobody_tuned')).toBe(AMBER);
  });
});
