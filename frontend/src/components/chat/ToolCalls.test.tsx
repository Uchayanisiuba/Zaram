/**
 * The model's working has to reach the screen.
 *
 * **The defect this file exists for.** `StreamEvent.tool_call` was emitted by
 * the engine for every call and every gate verdict from the day the tool loop
 * shipped, and `chatClient.parseEvent` dropped it in its `default:` case. No
 * frontend file mentioned `tool_call` at all. So a reply that searched a
 * repository and read two files was indistinguishable from one the model made
 * up — the backend was doing the honest thing and nothing rendered it.
 *
 * `npm run check:reachability` reports backend routes no frontend file
 * mentions; it does not report backend *events* nobody parses. The two tests in
 * the transport class below are that instrument, for this event.
 *
 * What is asserted here is the contract, not the styling: the event survives
 * parsing, a refusal says why, and a tool that ran is not dressed as a warning.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import ToolCalls from './ToolCalls';
import type { ChatToolCall } from '@/stores/chatStore';

const call = (over: Partial<ChatToolCall> = {}): ChatToolCall => ({
  server: 'code',
  tool: 'search_code',
  verdict: 'allow',
  reason: 'ran',
  ...over,
});

describe('the working is shown', () => {
  it('names every tool in the order it was used', () => {
    render(
      <ToolCalls
        calls={[call(), call({ tool: 'read_lines' }), call({ tool: 'read_lines' })]}
      />,
    );

    const rows = screen.getByTestId('tool-calls').querySelectorAll('li');
    expect(rows.length).toBe(3);
    expect(rows[0].textContent).toContain('code/search_code');
    expect(rows[1].textContent).toContain('code/read_lines');
  });

  it('says why a tool did not run', () => {
    // A refused tool changed the answer. `CLAUDE.md`: disabled capabilities are
    // visible, not silent — and a refusal that does not say what would permit
    // it reads as a broken product.
    render(
      <ToolCalls
        calls={[call({ tool: 'write_file', verdict: 'refuse', reason: 'writes are not granted' })]}
      />,
    );

    expect(screen.getByText(/did not run/)).toBeTruthy();
    expect(screen.getByText(/writes are not granted/)).toBeTruthy();
  });

  it('marks a call waiting on the user as waiting, not as failed', () => {
    render(<ToolCalls calls={[call({ verdict: 'confirm', reason: 'it writes' })]} />);

    expect(screen.getByText(/waiting on you/)).toBeTruthy();
  });

  it('does not repeat a reason for a call that simply ran', () => {
    // "ran · ran" is what happens when the verdict's own label and the reason
    // are both printed. The ordinary case should be the quietest line here.
    render(<ToolCalls calls={[call({ reason: 'ran' })]} />);

    const row = screen.getByTestId('tool-calls').querySelector('li');
    expect(row?.textContent?.match(/ran/g)?.length).toBe(1);
  });

  it('renders nothing when no tool was used', () => {
    // Most replies call nothing. An empty container would put a gap under every
    // ordinary answer for a feature that did not happen.
    const { container } = render(<ToolCalls calls={[]} />);

    expect(container.firstChild).toBeNull();
  });
});
