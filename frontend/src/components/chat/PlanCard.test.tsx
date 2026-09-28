/**
 * The checklist under the reply: rendered from the record, ticks by status,
 * and offers Go only when the loop paused for it.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';

import PlanCard from './PlanCard';

const items = [
  { text: 'Read the failing test', status: 'done' },
  { text: 'Fix add()', status: 'doing' },
  { text: 'Refactor helpers', status: 'skipped', reason: 'out of scope' },
  { text: 'Run the tests', status: 'todo' },
];

describe('PlanCard', () => {
  it('renders every item with its status and counts the done ones', () => {
    render(<PlanCard items={items} />);
    expect(screen.getByText('1/4 done')).toBeTruthy();
    expect(screen.getByText('out of scope', { exact: false })).toBeTruthy();
    expect(document.querySelectorAll('[data-status="done"]').length).toBe(1);
    expect(screen.queryByTestId('plan-go')).toBeNull();
  });

  it('offers Go only when the loop paused for it', () => {
    const onGo = vi.fn();
    render(<PlanCard items={items} awaitingGo onGo={onGo} />);
    fireEvent.click(screen.getByTestId('plan-go'));
    expect(onGo).toHaveBeenCalledTimes(1);
  });

  it('names which rung was pressed, so plain Go never asks for the louder one', () => {
    // The two are one button apart on screen and a long way apart in what
    // they permit; a card that reported the wrong one would hand over an
    // uninterrupted run for a press that asked to be stopped at each change.
    const onGo = vi.fn();
    render(<PlanCard items={items} awaitingGo onGo={onGo} />);
    fireEvent.click(screen.getByTestId('plan-go'));
    expect(onGo).toHaveBeenLastCalledWith('ask');
    fireEvent.click(screen.getByTestId('plan-go-full'));
    expect(onGo).toHaveBeenLastCalledWith('full');
  });

  it('says what the second rung costs, and that deletions still ask', () => {
    render(<PlanCard items={items} awaitingGo onGo={vi.fn()} />);
    expect(screen.getByText(/deletions still ask/i)).toBeTruthy();
  });

  it('offers neither rung when the loop did not pause', () => {
    render(<PlanCard items={items} />);
    expect(screen.queryByTestId('plan-go-full')).toBeNull();
  });

  it('renders nothing for an empty list', () => {
    const { container } = render(<PlanCard items={[]} />);
    expect(container.innerHTML).toBe('');
  });
});

/** **The claim and the evidence, on one card.**
 *
 * The maintainer's direction, 28 September 2026: an agent's output to a person
 * should be verifiable deliverables, not a stream of tool invocations. The
 * checklist was the claim and the tool rows were the evidence, and nothing
 * joined them — a nine-step task showed nine promises above twenty anonymous
 * rows. `planStep` is that join, decided by the backend at the moment of each
 * call, and these are the properties that make it a record rather than a
 * decoration.
 */
describe('PlanCard, showing what was actually run', () => {
  const calls = [
    { server: 'code', tool: 'read_file', verdict: 'allow', reason: '', target: 'app.py', planStep: 1 },
    { server: 'code', tool: 'write_file', verdict: 'allow', reason: '', target: 'app.py', planStep: 1 },
    { server: 'code', tool: 'run_command', verdict: 'refuse', reason: 'not granted', target: 'rm -rf /', planStep: 3 },
    { server: 'code', tool: 'search_code', verdict: 'allow', reason: '', target: 'add(' },
  ];

  it('nests each call under the step it was made for', () => {
    render(<PlanCard items={items} toolCalls={calls} />);
    const under = screen.getByTestId('plan-evidence-1');
    expect(under.textContent).toContain('read_file app.py');
    expect(under.textContent).toContain('write_file app.py');
  });

  it('shows what the call was aimed at, because that is the checkable half', () => {
    render(<PlanCard items={items} toolCalls={calls} />);
    // "read a file" is not a claim anybody can check; the path is.
    expect(screen.getByTestId('plan-evidence-1').textContent).toContain('app.py');
  });

  it('says so when the gate refused, under a step that claims otherwise', () => {
    render(<PlanCard items={items} toolCalls={calls} />);
    const under = screen.getByTestId('plan-evidence-3');
    expect(under.textContent).toContain('refused');
    expect(under.querySelector('[data-verdict="refuse"]')).toBeTruthy();
  });

  it('leaves a call belonging to no step to the interleaved rows', () => {
    render(<PlanCard items={items} toolCalls={calls} />);
    // `search_code` carries no `planStep`; it must not be filed under step 0,
    // which would be a claim the backend did not make.
    expect(screen.queryByTestId('plan-evidence-0')).toBeNull();
  });

  it('is the plain checklist when nothing ran', () => {
    render(<PlanCard items={items} />);
    expect(screen.queryByTestId('plan-evidence-1')).toBeNull();
  });
});
