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
