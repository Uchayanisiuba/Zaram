/**
 * The activity panel: what it opens to, and the claim it refuses to make.
 *
 * Asked for against Claude Code's *Background tasks* panel, which opens to the
 * individual task and the files being edited. Two of those three words survive
 * the trip: Zaram's code pack reads and never writes, so the panel says what
 * was read and says so out loud rather than leaving a reader to assume.
 */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('@/services/egressClient', () => ({ fetchEgressForStep: vi.fn(async () => []) }));

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

  it('says where a change and an egress can be checked, and no longer claims nothing was edited', () => {
    // Until 19 September 2026 this asserted "does not edit files — every
    // mutative tool is out of scope until v1". `write_file` and `edit_file`
    // shipped on 12 September, so the footer had been a false claim on the
    // one panel whose job is to say what happened.
    render(<ActivityPanel calls={[call()]} onClose={() => {}} />);

    expect(screen.queryByText(/does not edit files/)).toBeNull();
    expect(screen.getByText(/egress log/)).toBeTruthy();
  });

  it('a plan step reads by its own phrase', () => {
    render(
      <ActivityPanel
        calls={[call({ server: 'zaram', tool: 'knowledge.search', label: 'Searched the web', target: 'fable outage', reason: '4 results' })]}
        onClose={() => {}}
      />,
    );
    expect(screen.getByText('Searched the web')).toBeTruthy();
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

describe('what one step sent — 19 September 2026', () => {
  it('shows the focused step’s change with Revert, and asks the log what it sent', async () => {
    const { fetchEgressForStep } = await import('@/services/egressClient');
    vi.mocked(fetchEgressForStep).mockResolvedValue([
      { id: 'e1', at: 1, kind: 'request', host: 'api.github.com', method: 'GET', url: 'https://api.github.com/x', body: null, literalText: 'x', bytes: 240, decision: 'allowed', reason: '', source: 'client:github', meta: {} },
    ] as never);
    const focused = call({ tool: 'edit_file', target: 'a.py', diff: '--- a\n+++ b\n-x\n+y', commit: 'abc', stepId: 'c:0:call:2' });
    render(<ActivityPanel calls={[call(), focused]} focus={focused} onClose={() => {}} />);

    expect(document.querySelector('[data-focus="true"]')).not.toBeNull();
    expect(screen.getByTestId('change-card')).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId('step-egress')).toBeTruthy());
    expect(screen.getByTestId('step-egress').textContent).toContain('api.github.com');
    expect(screen.getByTestId('step-egress').textContent).toContain('240 bytes');
    expect(fetchEgressForStep).toHaveBeenCalledWith('c:0:call:2');
  });

  it('says plainly when a step sent nothing', async () => {
    const { fetchEgressForStep } = await import('@/services/egressClient');
    vi.mocked(fetchEgressForStep).mockResolvedValue([] as never);
    const focused = call({ stepId: 'c:0:call:1' });
    render(<ActivityPanel calls={[focused]} focus={focused} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByTestId('step-egress-none')).toBeTruthy());
  });

  it('a row can be opened out from inside the panel, after the fold — 20 September 2026', async () => {
    // Seen on screen: once the conversation's rows folded, their *open* went
    // with them, and the panel reached from the summary listed every call
    // with none openable — what a step sent was reachable only while it ran.
    const { fetchEgressForStep } = await import('@/services/egressClient');
    vi.mocked(fetchEgressForStep).mockClear();
    vi.mocked(fetchEgressForStep).mockResolvedValue([] as never);
    const first = call({ stepId: 'c:0:call:1', output: 'one' });
    const second = call({ tool: 'read_lines', stepId: 'c:0:call:2', output: 'two' });
    render(<ActivityPanel calls={[first, second]} onClose={() => {}} />);
    expect(document.querySelector('[data-focus="true"]')).toBeNull();

    await userEvent.click(screen.getAllByTestId('panel-call')[1]);

    expect(screen.getAllByTestId('panel-call')[1].getAttribute('data-focus')).toBe('true');
    await waitFor(() => expect(fetchEgressForStep).toHaveBeenCalledWith('c:0:call:2'));
    // Picking it again closes it.
    await userEvent.click(screen.getAllByTestId('panel-call')[1]);
    expect(document.querySelector('[data-focus="true"]')).toBeNull();
  });
});
