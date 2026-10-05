/**
 * @vitest-environment jsdom
 *
 * A terminal the person can see and type in.
 *
 * * **Both authors are shown and told apart** — Zaram's commands and yours.
 * * **It reads the one shell**, so what Zaram ran is on screen.
 * * **A refusal is a sentence**, not a blank panel.
 * * **It does not poll while closed** — an unopened panel costs nothing.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const readTerminal = vi.fn();
const typeInTerminal = vi.fn();
const stopTerminal = vi.fn();

vi.mock('@/services/terminalClient', () => ({
  readTerminal: (...a: unknown[]) => readTerminal(...a),
  typeInTerminal: (...a: unknown[]) => typeInTerminal(...a),
  stopTerminal: (...a: unknown[]) => stopTerminal(...a),
}));

import TerminalPanel from './TerminalPanel';

const line = (text: string, kind: 'command' | 'output', who: 'zaram' | 'user') => ({
  text,
  kind,
  who,
  at: 1,
});

const state = (lines: ReturnType<typeof line>[]) => ({ alive: true, cwd: 'C:\\work', lines });

beforeEach(() => {
  readTerminal.mockReset().mockResolvedValue(state([]));
  typeInTerminal.mockReset().mockResolvedValue(state([]));
  stopTerminal.mockReset().mockResolvedValue(true);
});
afterEach(() => cleanup());

const user = () => userEvent.setup();

async function open() {
  render(<TerminalPanel projectId="keyline" />);
  await user().click(screen.getByRole('button', { name: /open the terminal/i }));
}

describe('opening', () => {
  it('reads nothing until it is opened', () => {
    render(<TerminalPanel projectId="keyline" />);
    expect(readTerminal).not.toHaveBeenCalled();
  });

  it('shows what Zaram ran and what the person ran, told apart', async () => {
    readTerminal.mockResolvedValue(
      state([
        line('npm install', 'command', 'zaram'),
        line('added 12 packages', 'output', 'zaram'),
        line('git status', 'command', 'user'),
      ]),
    );
    await open();
    const commands = await screen.findAllByTestId('terminal-command');
    expect(commands[0]).toHaveTextContent('zaram');
    expect(commands[0]).toHaveTextContent('$ npm install');
    expect(commands[1]).toHaveTextContent('you');
    expect(screen.getByText('added 12 packages')).toBeInTheDocument();
  });

  it('says it is empty rather than showing a blank box', async () => {
    await open();
    expect(await screen.findByText(/nothing has been run yet/i)).toBeInTheDocument();
  });

  it('is honest that it is not a full terminal', async () => {
    await open();
    expect(await screen.findByText(/no colour, no cursor movement/i)).toBeInTheDocument();
  });

  it('turns a refusal into a sentence', async () => {
    readTerminal.mockRejectedValue(new Error('The terminal is off for this project.'));
    await open();
    expect(await screen.findByTestId('terminal-error')).toHaveTextContent('off for this project');
  });
});

describe('typing', () => {
  it('sends the command and shows the result', async () => {
    typeInTerminal.mockResolvedValue(
      state([line('echo hi', 'command', 'user'), line('hi', 'output', 'user')]),
    );
    await open();
    const u = user();
    await u.type(await screen.findByTestId('terminal-input'), 'echo hi{Enter}');
    await waitFor(() => expect(typeInTerminal).toHaveBeenCalledWith('keyline', 'echo hi'));
    expect(await screen.findByText('hi')).toBeInTheDocument();
  });

  it('sends nothing for an empty line', async () => {
    await open();
    await user().type(await screen.findByTestId('terminal-input'), '   {Enter}');
    expect(typeInTerminal).not.toHaveBeenCalled();
  });

  it('shows a failed command as a sentence and keeps working', async () => {
    typeInTerminal.mockRejectedValue(new Error('That command line is too long.'));
    await open();
    await user().type(await screen.findByTestId('terminal-input'), 'x{Enter}');
    expect(await screen.findByTestId('terminal-error')).toHaveTextContent('too long');
    expect(screen.getByTestId('terminal-input')).not.toBeDisabled();
  });
});

describe('stopping', () => {
  it('closes the shell and re-reads', async () => {
    await open();
    await screen.findByTestId('terminal-input');
    const before = readTerminal.mock.calls.length;
    await user().click(screen.getByRole('button', { name: /close the terminal and stop/i }));
    await waitFor(() => expect(stopTerminal).toHaveBeenCalledWith('keyline'));
    await waitFor(() => expect(readTerminal.mock.calls.length).toBeGreaterThan(before));
  });
});

describe('while open', () => {
  it('keeps reading, so a long command is watched', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      render(<TerminalPanel projectId="keyline" />);
      await act(async () => {
        screen.getByRole('button', { name: /open the terminal/i }).click();
      });
      const first = readTerminal.mock.calls.length;
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3200);
      });
      expect(readTerminal.mock.calls.length).toBeGreaterThan(first);
    } finally {
      vi.useRealTimers();
    }
  });
});
