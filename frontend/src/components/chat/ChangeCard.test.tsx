/**
 * A change to a file is shown, unfolded, with the button that reverses it.
 *
 * The write tools ship a diff and a commit on every `tool_call` that changed a
 * file, and the Project checkbox promises "a git commit you can revert". This
 * pins the card's contract: the diff renders as text, the counts are read off
 * it, and Revert calls the store with the project and the commit — then says
 * "reverted" or shows the backend's own sentence.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import ToolCalls from './ToolCalls';
import ChangeCard from './ChangeCard';
import { useChatStore } from '@/stores/chatStore';
import { useProjectStore } from '@/stores/projectStore';
import type { ChatToolCall } from '@/stores/chatStore';

const DIFF = [
  'diff --git a/calc.py b/calc.py',
  '--- a/calc.py',
  '+++ b/calc.py',
  '@@ -1,2 +1,2 @@',
  ' def add(a, b):',
  '-    return a - b',
  '+    return a + b',
].join('\n');

const change = (over: Partial<ChatToolCall> = {}): ChatToolCall => ({
  server: 'code',
  tool: 'edit_file',
  verdict: 'allow',
  reason: 'ran',
  target: 'calc.py',
  output: '{"commit": "abc123"}',
  diff: DIFF,
  commit: 'abc123',
  ...over,
});

describe('ChangeCard', () => {
  beforeEach(() => {
    useChatStore.setState({ projectId: 'app' });
  });

  it('renders the diff as text with the counts', () => {
    render(<ChangeCard call={change()} />);
    expect(screen.getByTestId('change-diff').textContent).toContain('-    return a - b');
    expect(screen.getByText('+1')).toBeTruthy();
    expect(screen.getByText('−1')).toBeTruthy();
    expect(screen.getByText('edited')).toBeTruthy();
  });

  it('reverts through the store and says so', async () => {
    const revertCommit = vi.fn().mockResolvedValue(null);
    useProjectStore.setState({ revertCommit });
    render(<ChangeCard call={change()} />);

    fireEvent.click(screen.getByTestId('change-revert'));

    await waitFor(() => expect(screen.getByTestId('change-reverted')).toBeTruthy());
    expect(revertCommit).toHaveBeenCalledWith('app', 'abc123');
    expect(screen.queryByTestId('change-revert')).toBeNull();
  });

  it("shows the backend's own sentence when the revert is refused", async () => {
    useProjectStore.setState({
      revertCommit: vi.fn().mockResolvedValue('could not revert: your local changes would be overwritten'),
    });
    render(<ChangeCard call={change()} />);

    fireEvent.click(screen.getByTestId('change-revert'));

    await waitFor(() =>
      expect(screen.getByTestId('change-revert-failed').textContent).toContain('local changes'),
    );
  });

  it('offers no revert without a project to revert in', () => {
    useChatStore.setState({ projectId: null });
    render(<ChangeCard call={change()} />);
    expect(screen.queryByTestId('change-revert')).toBeNull();
  });
});

describe('ToolCalls with a change', () => {
  it('never folds a change, and phrases the new tools', () => {
    render(
      <ToolCalls
        calls={[
          change({ tool: 'read_lines', target: 'calc.py', diff: undefined, commit: undefined }),
          change(),
          change({ tool: 'run_command', target: 'pytest', diff: undefined, commit: undefined }),
        ]}
      />,
    );
    // Folded summary for the reads and runs; the change is on screen regardless.
    expect(screen.getByTestId('tool-summary').textContent).toContain('edited a file');
    expect(screen.getByTestId('tool-summary').textContent).toContain('ran a command');
    expect(screen.getByTestId('change-card')).toBeTruthy();
    expect(screen.getByTestId('change-diff')).toBeTruthy();
  });
});
