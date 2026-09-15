/**
 * The answer to "this needs your say-so", on the row that says it.
 *
 * Before 15 September 2026 there was none: a held tool stopped the loop and
 * the only way through was Settings → Tools, finding the server and granting
 * the tool by name. These tests hold the two ends of the fix — the button
 * appears exactly where a grant would settle it, and never where a grant
 * would change nothing.
 *
 * The second is the one that matters. `grantable` is the gate's answer, and a
 * destructive tool keeps asking however much has been granted; a button
 * offering to allow it would promise something the gate will not honour, and
 * the person would press it, watch nothing change, and conclude the product
 * is broken.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

vi.mock('@/services/toolsClient', () => ({ grantTool: vi.fn(async () => ['imap_send_email']) }));

import { grantTool } from '@/services/toolsClient';
import ToolCalls from './ToolCalls';
import type { ChatToolCall } from '../../stores/chatStore';

const held = (over: Partial<ChatToolCall> = {}): ChatToolCall => ({
  server: 'email',
  tool: 'imap_send_email',
  verdict: 'confirm',
  reason: 'imap_send_email changes something.',
  target: 'to: client@example.com',
  grantable: true,
  ...over,
});

beforeEach(() => vi.mocked(grantTool).mockClear());

describe('allowing a held tool', () => {
  it('offers to allow the tool the gate is holding', () => {
    render(<ToolCalls calls={[held()]} onAllowed={vi.fn()} />);
    expect(screen.getByTestId('allow-tool').textContent).toContain('imap_send_email');
    expect(screen.getByText(/stop asking about it/)).toBeTruthy();
  });

  it('never offers to allow a deletion, because the gate would still ask', () => {
    render(<ToolCalls calls={[held({ tool: 'imap_delete_email', grantable: false })]} onAllowed={vi.fn()} />);
    expect(screen.queryByTestId('allow-tool')).toBeNull();
  });

  it('offers nothing on a call that ran or was refused', () => {
    render(
      <ToolCalls
        calls={[held({ verdict: 'allow' }), held({ verdict: 'refuse', tool: 'write_file' })]}
        onAllowed={vi.fn()}
      />,
    );
    expect(screen.queryByTestId('allow-tool')).toBeNull();
  });

  it('grants the tool and asks the question again', async () => {
    const onAllowed = vi.fn();
    render(<ToolCalls calls={[held()]} onAllowed={onAllowed} />);

    fireEvent.click(screen.getByTestId('allow-tool'));

    await waitFor(() => expect(onAllowed).toHaveBeenCalledTimes(1));
    expect(grantTool).toHaveBeenCalledWith('email', 'imap_send_email');
  });

  it('says so when the grant did not save, and does not pretend it worked', async () => {
    vi.mocked(grantTool).mockRejectedValueOnce(new Error('offline'));
    const onAllowed = vi.fn();
    render(<ToolCalls calls={[held()]} onAllowed={onAllowed} />);

    fireEvent.click(screen.getByTestId('allow-tool'));

    await waitFor(() => expect(screen.getByText(/did not save/)).toBeTruthy());
    // Asking again after a failed grant would run into the same gate and read
    // as the button doing nothing.
    expect(onAllowed).not.toHaveBeenCalled();
  });

  it('shows no button at all where the shell cannot retry', () => {
    // A replayed history: allowing settles nothing to ask again.
    render(<ToolCalls calls={[held()]} />);
    expect(screen.queryByTestId('allow-tool')).toBeNull();
  });
});
