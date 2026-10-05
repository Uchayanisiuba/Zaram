/**
 * @vitest-environment jsdom
 *
 * Activity's per-destination controls for a repository.
 *
 * A push is refused with "allow repositories to {host} in Activity", so the row
 * that does it has to exist — a refusal whose remedy is on no screen is the
 * failure the image row was added to fix.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const setEgressPolicy = vi.fn();

const entry = (host: string, source: string) => ({
  id: host + source,
  at: Date.now() / 1000,
  host,
  method: 'POST',
  url: `https://${host}/`,
  decision: 'denied',
  reason: 'x',
  source,
  kind: 'request',
  bytes: 0,
  body: null,
  stepId: '',
});

vi.mock('@/services/egressClient', () => ({
  applyRetention: vi.fn(),
  fetchEgressLog: async () => ({
    entries: [entry('github.com', 'code.git_push'), entry('example.org', 'chat')],
    total: 2,
  }),
  fetchEgressPolicy: async () => ({
    rules: {},
    classRules: {},
    hostsSeen: ['github.com', 'example.org'],
    hostsWithoutARule: ['github.com', 'example.org'],
    canDrawAt: [],
    browseAllowed: false,
  }),
  forgetEgressPolicy: vi.fn(),
  setEgressPolicy: (...a: unknown[]) => setEgressPolicy(...a),
  verifyEgressLog: async () => ({ ok: true, entries: 2, brokenAt: null }),
}));

vi.mock('@/components/tasks/TaskLists', () => ({ UnfinishedSection: () => null }));
vi.mock('@/components/tasks/RunsSection', () => ({ RunsSection: () => null }));

import ActivityWorkspace from './ActivityWorkspace';

beforeEach(() => setEgressPolicy.mockReset().mockResolvedValue(undefined));
afterEach(() => cleanup());

describe('the repository row', () => {
  it('is offered for a destination a push has reached', async () => {
    render(<ActivityWorkspace />);
    expect(await screen.findByTestId('repos-github.com')).toBeInTheDocument();
  });

  it('is not offered for a destination nothing was pushed to', async () => {
    render(<ActivityWorkspace />);
    await screen.findByTestId('repos-github.com');
    expect(screen.queryByTestId('repos-example.org')).toBeNull();
  });

  it('grants the repository class and nothing else', async () => {
    render(<ActivityWorkspace />);
    const row = await screen.findByTestId('repos-github.com');
    const allow = [...row.querySelectorAll('button')].find((b) => b.textContent === 'allow')!;
    await userEvent.setup().click(allow);
    await waitFor(() => expect(setEgressPolicy).toHaveBeenCalledWith('github.com', 'allow', 'repo'));
    expect(setEgressPolicy).toHaveBeenCalledTimes(1);
  });
});
