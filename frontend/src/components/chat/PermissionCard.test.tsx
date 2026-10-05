/**
 * @vitest-environment jsdom
 *
 * The card Zaram shows when it has stopped and is waiting on a person.
 *
 * The rungs were already right — `AllowTool` offered *for this
 * conversation* and *always*, and rule 7j's reasoning behind them is
 * unchanged. What this file covers is what was added: a way to say no, a
 * project rung for the grant the maintainer decided should be per project,
 * and the refusal to offer a button that would settle nothing.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const allowToolForSession = vi.fn(async () => []);
const grantTool = vi.fn(async () => []);
const setShell = vi.fn(async () => {});
const setWrites = vi.fn(async () => {});
const setRuns = vi.fn(async () => {});
const setDrives = vi.fn(async () => {});

vi.mock('@/services/toolsClient', () => ({
  allowToolForSession: (...a: unknown[]) => allowToolForSession(...(a as [])),
  grantTool: (...a: unknown[]) => grantTool(...(a as [])),
}));

let projectId: string | null = 'ride-share';

vi.mock('@/stores/chatStore', () => ({
  useChatStore: (select: (s: unknown) => unknown) =>
    select({ sessionId: 'session-1', projectId }),
}));

vi.mock('@/stores/projectStore', () => ({
  useProjectStore: (select: (s: unknown) => unknown) =>
    select({ setShell, setWrites, setRuns, setDrives }),
}));

import PermissionCard from './PermissionCard';

function held(over: Record<string, unknown> = {}) {
  return {
    server: 'code',
    tool: 'run_in_terminal',
    verdict: 'confirm',
    reason: 'Running terminal commands needs your say-so.',
    target: 'npm install',
    output: '',
    at: 0,
    grantable: true,
    grantScope: 'shell',
    ...over,
  } as never;
}

beforeEach(() => {
  projectId = 'ride-share';
  for (const fn of [allowToolForSession, grantTool, setShell, setWrites, setRuns, setDrives]) {
    fn.mockClear();
  }
});

afterEach(() => cleanup());

const user = () => userEvent.setup();

describe('what it says', () => {
  it('leads with the backend sentence, not one composed here', () => {
    // It already names what the tool does and what would permit it. A
    // second phrasing would be a second opinion about what was refused.
    render(<PermissionCard call={held()} onAllowed={vi.fn()} />);
    expect(screen.getByText('Running terminal commands needs your say-so.')).toBeTruthy();
  });

  it('shows what the call was aimed at', () => {
    // That a tool ran is not checkable; what it ran on is.
    render(<PermissionCard call={held()} onAllowed={vi.fn()} />);
    expect(screen.getByText('npm install')).toBeTruthy();
  });

  it('is not shown for a call that already ran', () => {
    render(<PermissionCard call={held({ verdict: 'allow' })} onAllowed={vi.fn()} />);
    expect(screen.queryByTestId('permission-card')).toBeNull();
  });
});

describe('the rungs', () => {
  it('allows for this conversation without writing anything to disk', async () => {
    const onAllowed = vi.fn();
    render(<PermissionCard call={held()} onAllowed={onAllowed} />);
    await user().click(screen.getByTestId('allow-tool-session'));
    await waitFor(() => expect(onAllowed).toHaveBeenCalled());
    expect(allowToolForSession).toHaveBeenCalledWith('code', 'run_in_terminal', 'session-1');
    expect(grantTool).not.toHaveBeenCalled();
    expect(setShell).not.toHaveBeenCalled();
  });

  it('allows for the project by flipping the switch the gate named', async () => {
    // The maintainer's own decision about the terminal: once the user
    // grants it permission, the permission is per project.
    const onAllowed = vi.fn();
    render(<PermissionCard call={held()} onAllowed={onAllowed} />);
    await user().click(screen.getByTestId('allow-tool-project'));
    await waitFor(() => expect(onAllowed).toHaveBeenCalled());
    expect(setShell).toHaveBeenCalledWith('ride-share', true);
  });

  it('flips the right switch for a different kind of tool', async () => {
    render(
      <PermissionCard
        call={held({ tool: 'write_file', grantScope: 'writes' })}
        onAllowed={vi.fn()}
      />,
    );
    await user().click(screen.getByTestId('allow-tool-project'));
    await waitFor(() => expect(setWrites).toHaveBeenCalledWith('ride-share', true));
    expect(setShell).not.toHaveBeenCalled();
  });

  it('allows always', async () => {
    render(<PermissionCard call={held()} onAllowed={vi.fn()} />);
    await user().click(screen.getByTestId('allow-tool'));
    await waitFor(() => expect(grantTool).toHaveBeenCalledWith('code', 'run_in_terminal'));
  });

  it('says what the project rung turns on, in words', () => {
    // "Always" without "stops asking everywhere" is the offer without the
    // deal.
    render(<PermissionCard call={held()} onAllowed={vi.fn()} />);
    expect(screen.getByText(/run terminal commands/)).toBeTruthy();
  });
});

describe('the project rung is not always offered', () => {
  it('is absent with no project open, because it would settle nothing', () => {
    projectId = null;
    render(<PermissionCard call={held()} onAllowed={vi.fn()} />);
    expect(screen.queryByTestId('allow-tool-project')).toBeNull();
    expect(screen.getByTestId('allow-tool-session')).toBeTruthy();
  });

  it('is absent when the gate named no switch', () => {
    // An attached MCP server is not inside anybody's project.
    render(
      <PermissionCard
        call={held({ server: 'weather', grantScope: '' })}
        onAllowed={vi.fn()}
      />,
    );
    expect(screen.queryByTestId('allow-tool-project')).toBeNull();
  });
});

describe('a tool no grant would settle', () => {
  /** `grantable` comes from the gate, which keeps asking about deletions
   *  however much has been granted. A button that changes nothing is
   *  worse than no button. */
  it('offers no allow at all', () => {
    render(
      <PermissionCard call={held({ tool: 'delete_file', grantable: false })} onAllowed={vi.fn()} />,
    );
    expect(screen.queryByTestId('allow-tool')).toBeNull();
    expect(screen.queryByTestId('allow-tool-session')).toBeNull();
    expect(screen.queryByTestId('allow-tool-project')).toBeNull();
  });

  it('still asks, and says why it will keep asking', () => {
    render(
      <PermissionCard call={held({ tool: 'delete_file', grantable: false })} onAllowed={vi.fn()} />,
    );
    expect(screen.getByTestId('permission-card')).toBeTruthy();
    expect(screen.getByTestId('deny-tool')).toBeTruthy();
    expect(screen.getByText(/every time/)).toBeTruthy();
  });
});

describe('saying no', () => {
  it('clears the question and sends nothing', async () => {
    // The gate already refused the call and the reply went on without it.
    // This answers the person, not the backend, and the label says so.
    render(<PermissionCard call={held()} onAllowed={vi.fn()} />);
    await user().click(screen.getByTestId('deny-tool'));
    expect(screen.queryByTestId('permission-card')).toBeNull();
    expect(allowToolForSession).not.toHaveBeenCalled();
    expect(grantTool).not.toHaveBeenCalled();
  });
});

describe('when a grant does not save', () => {
  it('says so rather than looking like it worked', async () => {
    allowToolForSession.mockRejectedValueOnce(new Error('offline'));
    const onAllowed = vi.fn();
    render(<PermissionCard call={held()} onAllowed={onAllowed} />);
    await user().click(screen.getByTestId('allow-tool-session'));
    await waitFor(() => expect(screen.getByText(/did not save/)).toBeTruthy());
    expect(onAllowed).not.toHaveBeenCalled();
  });
});

describe('run this once', () => {
  it('is offered for a call the gate will not let a grant settle, and grants nothing', async () => {
    // An install always asks: not grantable, so before this the card
    // offered only Deny. A yes for this one call is the answer that fits.
    const onAllowed = vi.fn();
    render(
      <PermissionCard
        call={held({ grantable: false, grantScope: '', once: true, heldTask: 'plan-7' })}
        onAllowed={onAllowed}
      />,
    );
    expect(screen.queryByTestId('allow-tool')).toBeNull();

    await user().click(screen.getByTestId('run-once'));

    expect(onAllowed).toHaveBeenCalledWith({ planId: 'plan-7', runHeld: true });
    for (const fn of [allowToolForSession, grantTool, setShell, setWrites, setRuns, setDrives]) {
      expect(fn).not.toHaveBeenCalled();
    }
  });

  it('is not offered when the backend says no, or when there is no task to carry on', () => {
    render(<PermissionCard call={held({ once: false, heldTask: 'plan-7' })} onAllowed={vi.fn()} />);
    expect(screen.queryByTestId('run-once')).toBeNull();
    cleanup();
    render(<PermissionCard call={held({ once: true })} onAllowed={vi.fn()} />);
    expect(screen.queryByTestId('run-once')).toBeNull();
  });

  it('a grant carries the parked task on too, without confirming the call', async () => {
    const onAllowed = vi.fn();
    render(<PermissionCard call={held({ once: true, heldTask: 'plan-7' })} onAllowed={onAllowed} />);

    await user().click(screen.getByTestId('allow-tool-session'));

    await waitFor(() => expect(onAllowed).toHaveBeenCalledWith({ planId: 'plan-7', runHeld: false }));
  });
});
