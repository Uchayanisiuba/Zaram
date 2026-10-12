/**
 * The GitHub section: connect by device code, say what is stored where, and never
 * touch a credential.
 *
 * Asked for 12 October 2026 -- the connection Claude and ChatGPT offer, with the
 * sign-in kept on this machine. What is pinned here is what a person reads and
 * presses: the code is shown, GitHub is opened by the shell bridge, the screen
 * finishes by itself, an unconfigured build says so rather than offering a button
 * that cannot work, and disconnecting says it does not revoke on GitHub.
 */
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const fetchGithubStatus = vi.fn();
const startGithubConnect = vi.fn();
const pollGithubConnect = vi.fn();
const disconnectGithub = vi.fn();
const fetchGithubRepositories = vi.fn();
const openInBrowser = vi.fn();

vi.mock('../../services/githubClient', () => ({
  fetchGithubStatus: () => fetchGithubStatus(),
  startGithubConnect: () => startGithubConnect(),
  pollGithubConnect: (flow: string) => pollGithubConnect(flow),
  disconnectGithub: () => disconnectGithub(),
  fetchGithubRepositories: () => fetchGithubRepositories(),
}));
vi.mock('../../lib/openInBrowser', () => ({ openInBrowser: (url: string) => openInBrowser(url) }));

import GitHubSection from './GitHubSection';

function Row({ label, value, detail, children }: { label: string; value?: string; detail?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div data-testid={`row-${label}`}>
      <span>{label}</span> <span>{value}</span>
      <div>{detail}</div>
      {children}
    </div>
  );
}

const base = {
  configured: true,
  connected: false,
  expired: false,
  login: '',
  expires_at: null,
  sealed: null,
  install_url: 'https://github.com/apps/zaram-app/installations/new',
  manage_url: 'https://github.com/settings/applications',
};
const connected = { ...base, connected: true, login: 'octo', sealed: true };

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(() => {
  vi.useRealTimers();
});

describe('before connecting', () => {
  it('offers Connect and says where the sign-in will live and what always asks', async () => {
    fetchGithubStatus.mockResolvedValue(base);
    render(<GitHubSection Row={Row} />);
    expect(await screen.findByRole('button', { name: 'Connect GitHub' })).toBeInTheDocument();
    const text = document.body.textContent ?? '';
    expect(text).toMatch(/stays on this computer/i);
    expect(text).toMatch(/asks you each time/i);
    expect(text).toMatch(/no standing yes/i);
  });

  it('says so, and offers no button, when the build has no app registered', async () => {
    fetchGithubStatus.mockResolvedValue({ ...base, configured: false });
    render(<GitHubSection Row={Row} />);
    expect(await screen.findByText(/no GitHub app registered/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Connect GitHub' })).toBeNull();
  });

  it('says an ended sign-in ended, rather than looking like a first visit', async () => {
    fetchGithubStatus.mockResolvedValue({ ...base, expired: true });
    render(<GitHubSection Row={Row} />);
    expect(await screen.findByText(/sign-in ended/i)).toBeInTheDocument();
  });

  it('reports a backend that cannot be reached instead of staying silent', async () => {
    fetchGithubStatus.mockRejectedValue(new Error('the backend is down'));
    render(<GitHubSection Row={Row} />);
    expect(await screen.findByText('the backend is down')).toBeInTheDocument();
  });
});

describe('connecting', () => {
  it('shows the code, opens GitHub through the shell bridge, and finishes by itself', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchGithubStatus.mockResolvedValue(base);
    startGithubConnect.mockResolvedValue({
      flow: 'f1', user_code: 'ABCD-1234', verification_uri: 'https://github.com/login/device', interval: 5, expires_in: 900,
    });
    pollGithubConnect
      .mockResolvedValueOnce({ state: 'pending' })
      .mockResolvedValueOnce({ state: 'done', ...connected });

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<GitHubSection Row={Row} />);
    await user.click(await screen.findByRole('button', { name: 'Connect GitHub' }));

    expect(await screen.findByText('ABCD-1234')).toBeInTheDocument();
    expect(document.body.textContent).toMatch(/password is never entered here/i);
    await user.click(screen.getByRole('button', { name: 'Open GitHub' }));
    expect(openInBrowser).toHaveBeenCalledWith('https://github.com/login/device');

    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(pollGithubConnect).toHaveBeenCalledWith('f1');
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(await screen.findByText('connected as octo')).toBeInTheDocument();
  });

  it('stops polling when cancelled, and a late answer does not revive it', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchGithubStatus.mockResolvedValue(base);
    startGithubConnect.mockResolvedValue({
      flow: 'f2', user_code: 'WXYZ-9999', verification_uri: 'https://github.com/login/device', interval: 5, expires_in: 900,
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<GitHubSection Row={Row} />);
    await user.click(await screen.findByRole('button', { name: 'Connect GitHub' }));
    await screen.findByText('WXYZ-9999');
    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(pollGithubConnect).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Connect GitHub' })).toBeInTheDocument();
  });

  it('says plainly when GitHub refused', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchGithubStatus.mockResolvedValue(base);
    startGithubConnect.mockResolvedValue({
      flow: 'f3', user_code: 'AAAA-0000', verification_uri: 'https://github.com/login/device', interval: 5, expires_in: 900,
    });
    pollGithubConnect.mockResolvedValue({ state: 'denied' });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<GitHubSection Row={Row} />);
    await user.click(await screen.findByRole('button', { name: 'Connect GitHub' }));
    await screen.findByText('AAAA-0000');
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(await screen.findByText(/the sign-in was refused/i)).toBeInTheDocument();
  });

  it('reports a start that failed, such as device sign-in being off', async () => {
    fetchGithubStatus.mockResolvedValue(base);
    startGithubConnect.mockRejectedValue(new Error("Device sign-in is switched off for the Zaram app on GitHub."));
    const user = userEvent.setup();
    render(<GitHubSection Row={Row} />);
    await user.click(await screen.findByRole('button', { name: 'Connect GitHub' }));
    expect(await screen.findByText(/switched off for the Zaram app/i)).toBeInTheDocument();
  });
});

describe('connected', () => {
  it('names the person, says it is sealed, and offers the three things to do', async () => {
    fetchGithubStatus.mockResolvedValue(connected);
    render(<GitHubSection Row={Row} />);
    expect(await screen.findByText('connected as octo')).toBeInTheDocument();
    expect(document.body.textContent).toMatch(/sealed to your Windows account/i);
    for (const name of ['Choose repositories', 'Show what Zaram can reach', 'Disconnect']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
  });

  it('does not claim a seal it does not have', async () => {
    fetchGithubStatus.mockResolvedValue({ ...connected, sealed: false });
    render(<GitHubSection Row={Row} />);
    await screen.findByText('connected as octo');
    expect(document.body.textContent).toMatch(/not encrypted on this system/i);
    expect(document.body.textContent).not.toMatch(/sealed to your Windows account/i);
  });

  it('opens the page where repositories are chosen', async () => {
    fetchGithubStatus.mockResolvedValue(connected);
    const user = userEvent.setup();
    render(<GitHubSection Row={Row} />);
    await user.click(await screen.findByRole('button', { name: 'Choose repositories' }));
    expect(openInBrowser).toHaveBeenCalledWith(base.install_url);
  });

  it('lists what Zaram can reach, marking private and read-only ones', async () => {
    fetchGithubStatus.mockResolvedValue(connected);
    fetchGithubRepositories.mockResolvedValue({
      repositories: [
        { full_name: 'octo/site', private: true, default_branch: 'main', can_push: true },
        { full_name: 'octo/docs', private: false, default_branch: 'main', can_push: false },
      ],
      install_url: base.install_url,
    });
    const user = userEvent.setup();
    render(<GitHubSection Row={Row} />);
    await user.click(await screen.findByRole('button', { name: 'Show what Zaram can reach' }));
    await waitFor(() => expect(document.body.textContent).toMatch(/octo\/site \(private\)/));
    expect(document.body.textContent).toMatch(/octo\/docs — read only/);
  });

  it('says there is nothing yet, and how to add something, when nothing is installed', async () => {
    fetchGithubStatus.mockResolvedValue(connected);
    fetchGithubRepositories.mockResolvedValue({ repositories: [], install_url: base.install_url });
    const user = userEvent.setup();
    render(<GitHubSection Row={Row} />);
    await user.click(await screen.findByRole('button', { name: 'Show what Zaram can reach' }));
    expect(await screen.findByText(/None yet/i)).toBeInTheDocument();
  });

  it('disconnecting forgets the sign-in and says it does not revoke it on GitHub', async () => {
    fetchGithubStatus.mockResolvedValue(connected);
    disconnectGithub.mockResolvedValue({
      ...base,
      note: 'Zaram has forgotten the sign-in. To withdraw its access on GitHub too, remove it at https://github.com/settings/applications.',
    });
    const user = userEvent.setup();
    render(<GitHubSection Row={Row} />);
    await user.click(await screen.findByRole('button', { name: 'Disconnect' }));
    expect(await screen.findByRole('button', { name: 'Connect GitHub' })).toBeInTheDocument();
    expect(document.body.textContent).toMatch(/withdraw its access on GitHub too/i);
  });
});

describe('what the screen never holds', () => {
  it('has no field for a password, a token or a key', async () => {
    fetchGithubStatus.mockResolvedValue(base);
    const { container } = render(<GitHubSection Row={Row} />);
    await screen.findByRole('button', { name: 'Connect GitHub' });
    expect(container.querySelectorAll('input, textarea')).toHaveLength(0);
  });
});
