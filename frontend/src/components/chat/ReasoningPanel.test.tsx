/**
 * Thinking is one quiet line by default, in the model's own words, with the
 * full text one click away — asked for on 19 September 2026 against Claude.
 */
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import ReasoningPanel from './ReasoningPanel';

const THOUGHT =
  'Okay, the user wants dark mode.\n\n' +
  'The reducer lives in store.ts. I should read it before touching the CSS.';

describe('ReasoningPanel', () => {
  it('is collapsed by default, while streaming and after', () => {
    const { rerender } = render(<ReasoningPanel text={THOUGHT} streaming />);
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText(/Okay, the user wants dark mode/)).toBeNull();

    rerender(<ReasoningPanel text={THOUGHT} streaming={false} />);
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false');
  });

  it('shows the opening of the latest paragraph as the line', () => {
    render(<ReasoningPanel text={THOUGHT} streaming />);
    expect(screen.getByTestId('reasoning-line')).toHaveTextContent(
      'The reducer lives in store.ts.',
    );
  });

  it('prefers the checklist item the model is doing', () => {
    render(<ReasoningPanel text={THOUGHT} streaming doing="Read the store" />);
    expect(screen.getByTestId('reasoning-line')).toHaveTextContent('Read the store');
  });

  it('opens to the full text on click and keeps the user’s choice', () => {
    const { rerender } = render(<ReasoningPanel text={THOUGHT} streaming />);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText(/Okay, the user wants dark mode/)).toBeInTheDocument();
    // The line is redundant with the text below it once open.
    expect(screen.queryByTestId('reasoning-line')).toBeNull();

    rerender(<ReasoningPanel text={THOUGHT} streaming={false} />);
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true');
  });

  it('says how long it thought only when it measured it', () => {
    const { rerender } = render(<ReasoningPanel text={THOUGHT} streaming />);
    expect(screen.getByRole('button')).toHaveTextContent(/^Thinking/);
    rerender(<ReasoningPanel text={THOUGHT} streaming={false} />);
    expect(screen.getByRole('button')).toHaveTextContent(/Thought for \d+ s/);
  });

  it('shows no duration for a message it never watched stream', () => {
    render(<ReasoningPanel text={THOUGHT} streaming={false} />);
    expect(screen.getByRole('button')).toHaveTextContent(/^Thought process/);
    expect(screen.getByRole('button')).not.toHaveTextContent(/Thought for/);
  });

  it('renders nothing without text', () => {
    const { container } = render(<ReasoningPanel text="" streaming />);
    expect(container.firstChild).toBeNull();
  });
});
