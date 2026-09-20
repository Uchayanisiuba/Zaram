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
import { fireEvent, render, screen } from '@testing-library/react';

import ToolCalls from './ToolCalls';
import type { ChatToolCall } from '@/stores/chatStore';

const call = (over: Partial<ChatToolCall> = {}): ChatToolCall => ({
  server: 'code',
  tool: 'search_code',
  verdict: 'allow',
  reason: 'ran',
  target: '',
  ...over,
});

describe('the working is shown', () => {
  it('summarises finished work in one line rather than listing it', async () => {
    // Folded once it is done, the shape Claude Code uses: a finished exchange
    // should read as prose rather than as a log. The detail is not lost, it
    // moves — the summary opens the activity panel, which has room for what
    // each call was aimed at. `ActivityPanel.test.tsx` asserts that half.
    render(
      <ToolCalls
        calls={[call(), call({ tool: 'read_lines' }), call({ tool: 'read_lines' })]}
      />,
    );

    expect(screen.getByTestId('tool-summary').textContent).toContain(
      'Searched code, read 2 files',
    );
    // Nothing enumerated in the conversation itself.
    expect(screen.getByTestId('tool-calls').querySelectorAll('li').length).toBe(0);
  });

  it('stays open while the work is still happening', () => {
    // A generation that may call a tool is buffered, so during a coding task
    // this is the only thing on screen. Folding live work would leave a summary
    // of what has happened and no sign that anything still is.
    render(<ToolCalls calls={[call()]} active />);

    expect(screen.getByTestId('tool-calls').querySelectorAll('li').length).toBe(1);
    expect(screen.getByTestId('tool-summary').getAttribute('aria-expanded')).toBe('true');
  });

  it('never folds a tool the gate stopped', () => {
    // The one thing deliberately not copied from Claude Code. Collapsing is for
    // work that went as asked; a refusal changed what the answer could be, and
    // "disabled capabilities are visible, not silent" is not a preference about
    // summaries. Rendered without anyone opening anything.
    render(
      <ToolCalls
        calls={[
          call(),
          call({ tool: 'write_file', verdict: 'refuse', reason: 'writes are not granted' }),
        ]}
      />,
    );

    expect(screen.getByText(/writes are not granted/)).toBeTruthy();
    // ...while the allowed call beside it is still folded away.
    expect(screen.queryByText('code/search_code')).toBeNull();
  });

  it('summarises only the tools that exist, and invents no verb for one that does not', () => {
    // There is no "wrote" or "patched" phrase, because there is no such tool:
    // every mutative tool is out of scope until v1 ships. An unrecognised tool
    // falls back to its own name rather than to a verb somebody guessed.
    render(<ToolCalls calls={[call({ tool: 'some_new_tool' })]} />);

    expect(screen.getByTestId('tool-summary').textContent).toContain('some_new_tool');
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
    render(<ToolCalls calls={[call({ reason: 'ran' })]} active />);

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

describe('a step opens to what it produced', () => {
  // Asked for 12 September 2026 against Claude Code: each step's output in a
  // bounded pane of its own, scrolled with the wheel, the transcript still.
  it('a step with output is a row that opens a bounded, scrolling pane', () => {
    render(
      <ToolCalls
        active
        calls={[call({ tool: 'read_lines', target: 'readiness.py:1-40', output: 'line one\nline two' })]}
      />,
    );
    const row = screen.getByTestId('step-row');
    expect(row.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByTestId('step-output')).toBeNull();

    fireEvent.click(row);

    const pane = screen.getByTestId('step-output');
    expect(pane.textContent).toBe('line one\nline two');
    expect(pane.style.overflow).toBe('auto');
    expect(pane.style.overscrollBehavior).toBe('contain');
    expect(pane.style.maxHeight).not.toBe('');
  });

  it('a step with nothing behind it is not a button', () => {
    render(<ToolCalls active calls={[call({ output: '' })]} />);
    const row = screen.getByTestId('step-row');
    expect(row.hasAttribute('aria-expanded')).toBe(false);
    expect((row as HTMLButtonElement).disabled).toBe(true);
  });

  it('output is rendered as text, never as markup', () => {
    render(<ToolCalls active calls={[call({ output: '<img src=x onerror=alert(1)>' })]} />);
    fireEvent.click(screen.getByTestId('step-row'));
    const pane = screen.getByTestId('step-output');
    expect(pane.querySelector('img')).toBeNull();
    expect(pane.textContent).toContain('<img');
  });
});

describe('a plan step on the same row — 19 September 2026', () => {
  const step = (over: Partial<ChatToolCall> = {}): ChatToolCall => ({
    server: 'zaram',
    tool: 'knowledge.search',
    verdict: 'allow',
    reason: '4 results',
    target: 'fable outage',
    label: 'Searched the web',
    doing: 'Searching the web',
    stepId: 's1',
    ...over,
  });

  it('reads as prose while it runs, with a spinner and no verdict word', () => {
    render(<ToolCalls calls={[step({ verdict: 'running', reason: '' })]} active />);

    expect(screen.getByTestId('step-phrase').textContent).toBe('Searching the web');
    expect(screen.getByTestId('step-row').textContent).toContain('“fable outage”');
    expect(screen.getByTestId('step-row').querySelector('.animate-spin')).not.toBeNull();
    expect(screen.getByTestId('step-row').textContent).not.toContain('ran');
  });

  it('settles to the past tense with its one detail', () => {
    render(<ToolCalls calls={[step()]} active />);

    const row = screen.getByTestId('step-row');
    expect(screen.getByTestId('step-phrase').textContent).toBe('Searched the web');
    expect(row.textContent).toContain('4 results');
    expect(row.querySelector('.animate-spin')).toBeNull();
  });

  it('folds by its own phrase, beside the tool verbs', () => {
    render(
      <ToolCalls
        calls={[
          step(),
          call({ tool: 'read_lines' }),
          call({ tool: 'read_lines' }),
          step({ tool: 'memory.recall', label: 'Recalled 3 facts', target: '', reason: '' }),
        ]}
      />,
    );

    expect(screen.getByTestId('tool-summary').textContent).toContain(
      'Searched the web, read 2 files, recalled 3 facts',
    );
  });

  it('a step that failed is never folded and says why', () => {
    render(<ToolCalls calls={[step({ verdict: 'refuse', reason: 'search is off' })]} />);

    expect(screen.queryByTestId('tool-summary')).toBeNull();
    expect(screen.getByTestId('step-row').textContent).toContain('search is off');
  });
});

describe('the working pane, from a row — 19 September 2026', () => {
  it('opens the panel focused on the row that was opened', () => {
    render(
      <ToolCalls
        calls={[call({ tool: 'read_lines', target: 'a.py', output: 'def f(): pass', stepId: 'c:0:call:1' })]}
        active
      />,
    );
    fireEvent.click(screen.getByTestId('open-step'));
    const panel = screen.getByTestId('activity-panel');
    expect(panel.querySelector('[data-focus="true"]')).not.toBeNull();
  });

  it('a step still running has nothing to open yet', () => {
    render(
      <ToolCalls
        calls={[call({ server: 'zaram', tool: 'knowledge.search', verdict: 'running', label: 'Searched the web', doing: 'Searching the web', stepId: 'c:0' })]}
        active
      />,
    );
    expect(screen.queryByTestId('open-step')).toBeNull();
  });
});
