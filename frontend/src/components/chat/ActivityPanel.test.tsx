/**
 * The activity panel: what it opens to, and the claim it refuses to make.
 *
 * Asked for against Claude Code's *Background tasks* panel, which opens to the
 * individual task and the files being edited. Two of those three words survive
 * the trip: Zaram's code pack reads and never writes, so the panel says what
 * was read and says so out loud rather than leaving a reader to assume.
 */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import ActivityPanel from './ActivityPanel';
import ToolCalls from './ToolCalls';
import type { ChatToolCall } from '@/stores/chatStore';

const call = (over: Partial<ChatToolCall> = {}): ChatToolCall => ({
  server: 'code',
  tool: 'read_lines',
  verdict: 'allow',
  reason: 'ran',
  target: 'backend/core/readiness.py:156-181',
  ...over,
});

afterEach(cleanup);

describe('what the panel opens to', () => {
  it('names what each call was aimed at, not just that one happened', () => {
    // `readiness.py:156-181` is checkable and "read a file" is not. Provenance
    // for code being a line range is the whole reason the chunker exists.
    render(<ActivityPanel calls={[call()]} onClose={() => {}} />);

    expect(screen.getByTestId('call-target').textContent).toBe(
      'backend/core/readiness.py:156-181',
    );
  });

  it('says plainly that nothing was edited', () => {
    // The claim the reference panel makes and this one must not. Every mutative
    // tool is out of scope until v1, so a reader who assumed otherwise would
    // believe their repository had been changed.
    render(<ActivityPanel calls={[call()]} onClose={() => {}} />);

    expect(screen.getByText(/does not edit files/)).toBeTruthy();
  });

  it('omits the target line for a call that named nothing', () => {
    // An empty monospace row under a tool would read as a path that failed to
    // load. Absent is the honest rendering of absent.
    render(<ActivityPanel calls={[call({ target: '' })]} onClose={() => {}} />);

    expect(screen.queryByTestId('call-target')).toBeNull();
  });

  it('closes on Escape', async () => {
    const onClose = vi.fn();
    render(<ActivityPanel calls={[call()]} onClose={onClose} />);

    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });
});

describe('how it is reached', () => {
  it('opens from the summary line once the work has finished', async () => {
    render(<ToolCalls calls={[call(), call({ tool: 'search_code', target: 'budget' })]} />);

    expect(screen.queryByTestId('activity-panel')).toBeNull();
    await userEvent.click(screen.getByTestId('tool-summary'));

    expect(screen.getByTestId('activity-panel')).toBeTruthy();
    expect(screen.getAllByTestId('call-target').length).toBe(2);
  });

  it('does not seize the screen while the work is still running', async () => {
    // Live work unfolds in the conversation instead. During a buffered
    // generation the tool line is the only thing on screen, and replacing the
    // conversation with an overlay would take it away at the moment it is the
    // only thing to read.
    render(<ToolCalls calls={[call()]} active />);

    await userEvent.click(screen.getByTestId('tool-summary'));
    expect(screen.queryByTestId('activity-panel')).toBeNull();
  });
});
