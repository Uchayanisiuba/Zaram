/**
 * The update card: the question once, and then only what is true.
 *
 * Asked for 14 October 2026. What is pinned is what a person would feel and what
 * the rules require: nothing is fetched while the answer is no or unasked, the
 * question says what a check sends, a download is never started or run without a
 * press, "Later" is for the session and never nags, and a build that cannot tell
 * which release it is shows nothing at all.
 */
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { UpdateStatus } from '@/services/updatesClient';

const fetchUpdateStatus = vi.fn();
const setUpdateChecks = vi.fn();
const checkForUpdates = vi.fn();
const startUpdateDownload = vi.fn();
const installUpdate = vi.fn();
const openInBrowser = vi.fn();

vi.mock('@/services/updatesClient', () => ({
  fetchUpdateStatus: () => fetchUpdateStatus(),
  setUpdateChecks: (on: boolean) => setUpdateChecks(on),
  checkForUpdates: (force: boolean) => checkForUpdates(force),
  startUpdateDownload: () => startUpdateDownload(),
  installUpdate: () => installUpdate(),
}));
vi.mock('@/lib/openInBrowser', () => ({ openInBrowser: (url: string) => openInBrowser(url) }));

import UpdateBanner from './UpdateBanner';
import { resetUpdateStoreForTests } from '@/stores/updateStore';

const release = {
  tag: 'v0.1.0-alpha.8',
  page: 'https://github.com/Uchayanisiuba/Zaram/releases/tag/v0.1.0-alpha.8',
  installer: { name: 'Zaram-0.1.0-x64.exe', url: 'https://github.com/x', size: 208539009 },
};

const base: UpdateStatus = {
  current: 'v0.1.0-alpha.7',
  known: true,
  checks: true,
  last_checked: 1,
  phase: 'up_to_date',
  latest: null,
  progress: { done: 0, total: 0 },
  error: '',
  ready: false,
  can_install: true,
  manual_reason: '',
  release_page: 'https://github.com/Uchayanisiuba/Zaram/releases',
};
const available: UpdateStatus = { ...base, phase: 'available', latest: release };
const ready: UpdateStatus = { ...available, phase: 'ready', ready: true };

beforeEach(() => {
  vi.clearAllMocks();
  resetUpdateStoreForTests();
});
afterEach(() => {
  vi.useRealTimers();
});

describe('when there is nothing to say', () => {
  it('shows nothing in a build that cannot tell which release it is', async () => {
    fetchUpdateStatus.mockResolvedValue({ ...base, current: null, known: false, checks: null });
    render(<UpdateBanner />);
    await waitFor(() => expect(fetchUpdateStatus).toHaveBeenCalled());
    expect(screen.queryByTestId('update-banner')).toBeNull();
  });

  it('shows nothing when up to date', async () => {
    fetchUpdateStatus.mockResolvedValue(base);
    checkForUpdates.mockResolvedValue(base);
    render(<UpdateBanner />);
    await waitFor(() => expect(checkForUpdates).toHaveBeenCalled());
    expect(screen.queryByTestId('update-banner')).toBeNull();
  });
});

describe('the question', () => {
  it('is asked when nobody has answered, says what a check sends, and fetches nothing', async () => {
    fetchUpdateStatus.mockResolvedValue({ ...base, checks: null });
    render(<UpdateBanner />);
    expect(await screen.findByTestId('update-ask')).toBeInTheDocument();
    const text = screen.getByTestId('update-banner').textContent ?? '';
    expect(text).toMatch(/list of releases/i);
    expect(text).toMatch(/nothing about you/i);
    expect(text).toMatch(/Activity/);
    expect(checkForUpdates).not.toHaveBeenCalled();
    expect(setUpdateChecks).not.toHaveBeenCalled();
  });

  it('yes records the answer and checks once, as an act', async () => {
    fetchUpdateStatus.mockResolvedValue({ ...base, checks: null });
    setUpdateChecks.mockResolvedValue({ ...base, checks: true });
    checkForUpdates.mockResolvedValue(available);
    render(<UpdateBanner />);
    await userEvent.click(await screen.findByTestId('update-yes'));
    await waitFor(() => expect(screen.getByTestId('update-available')).toBeInTheDocument());
    expect(setUpdateChecks).toHaveBeenCalledWith(true);
    expect(checkForUpdates).toHaveBeenCalledTimes(1);
    expect(checkForUpdates).toHaveBeenCalledWith(true);
  });

  it('no records the answer and fetches nothing, now or later', async () => {
    fetchUpdateStatus.mockResolvedValue({ ...base, checks: null });
    setUpdateChecks.mockResolvedValue({ ...base, checks: false });
    render(<UpdateBanner />);
    await userEvent.click(await screen.findByTestId('update-no'));
    await waitFor(() => expect(setUpdateChecks).toHaveBeenCalledWith(false));
    expect(checkForUpdates).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByTestId('update-banner')).toBeNull());
  });

  it('a person who said no is not checked for at launch, and is not asked again', async () => {
    fetchUpdateStatus.mockResolvedValue({ ...base, checks: false });
    render(<UpdateBanner />);
    await waitFor(() => expect(fetchUpdateStatus).toHaveBeenCalled());
    expect(checkForUpdates).not.toHaveBeenCalled();
    expect(screen.queryByTestId('update-ask')).toBeNull();
  });
});

describe('at launch', () => {
  it('a person who said yes is checked once, not forced', async () => {
    fetchUpdateStatus.mockResolvedValue(base);
    checkForUpdates.mockResolvedValue(available);
    const { rerender } = render(<UpdateBanner />);
    await screen.findByTestId('update-available');
    rerender(<UpdateBanner />);
    expect(checkForUpdates).toHaveBeenCalledTimes(1);
    expect(checkForUpdates).toHaveBeenCalledWith(false);
  });
});

describe('a newer build', () => {
  it('names it, puts the size on the button, and starts nothing by itself', async () => {
    fetchUpdateStatus.mockResolvedValue(available);
    checkForUpdates.mockResolvedValue(available);
    render(<UpdateBanner />);
    expect(await screen.findByText('v0.1.0-alpha.8 is available.')).toBeInTheDocument();
    expect(screen.getByTestId('update-download')).toHaveTextContent('Download 199 MB');
    expect(startUpdateDownload).not.toHaveBeenCalled();
    expect(installUpdate).not.toHaveBeenCalled();
  });

  it('opens the release notes through the shell bridge', async () => {
    fetchUpdateStatus.mockResolvedValue(available);
    checkForUpdates.mockResolvedValue(available);
    render(<UpdateBanner />);
    await userEvent.click(await screen.findByTestId('update-notes'));
    expect(openInBrowser).toHaveBeenCalledWith(release.page);
  });

  it('Later puts it away for the session', async () => {
    fetchUpdateStatus.mockResolvedValue(available);
    checkForUpdates.mockResolvedValue(available);
    render(<UpdateBanner />);
    await userEvent.click(await screen.findByTestId('update-later'));
    expect(screen.queryByTestId('update-banner')).toBeNull();
  });

  it('a portable build is sent to the release page and offered no download', async () => {
    const portable = { ...available, can_install: false, manual_reason: 'This is the portable build, which cannot replace itself.' };
    fetchUpdateStatus.mockResolvedValue(portable);
    checkForUpdates.mockResolvedValue(portable);
    render(<UpdateBanner />);
    await userEvent.click(await screen.findByTestId('update-page'));
    expect(openInBrowser).toHaveBeenCalledWith(release.page);
    expect(screen.queryByTestId('update-download')).toBeNull();
  });
});

describe('downloading and installing', () => {
  it('pressing Download starts it, shows progress, and offers install when it is done', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchUpdateStatus
      .mockResolvedValueOnce(available)
      .mockResolvedValueOnce({ ...available, phase: 'downloading', progress: { done: 50, total: 100 } })
      .mockResolvedValue(ready);
    checkForUpdates.mockResolvedValue(available);
    startUpdateDownload.mockResolvedValue({ ...available, phase: 'downloading', progress: { done: 0, total: 100 } });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<UpdateBanner />);
    await user.click(await screen.findByTestId('update-download'));
    expect(startUpdateDownload).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(await screen.findByText(/Downloading v0\.1\.0-alpha\.8 — 50%/)).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '50');
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(await screen.findByTestId('update-install')).toBeInTheDocument();
  });

  it('Restart and install says Zaram will close, and runs only on the press', async () => {
    fetchUpdateStatus.mockResolvedValue(ready);
    checkForUpdates.mockResolvedValue(ready);
    installUpdate.mockResolvedValue({ ok: true });
    render(<UpdateBanner />);
    const button = await screen.findByTestId('update-install');
    expect(screen.getByTestId('update-banner').textContent).toMatch(/close, update and open again/i);
    expect(screen.getByTestId('update-banner').textContent).toMatch(/memory and settings are kept/i);
    expect(installUpdate).not.toHaveBeenCalled();
    await userEvent.click(button);
    expect(installUpdate).toHaveBeenCalledTimes(1);
  });

  it('an installer the shell refused is said in the shell’s words', async () => {
    fetchUpdateStatus.mockResolvedValue(ready);
    checkForUpdates.mockResolvedValue(ready);
    installUpdate.mockResolvedValue({ ok: false, reason: 'The downloaded update changed on disk after it was checked, so it was not run.' });
    render(<UpdateBanner />);
    await userEvent.click(await screen.findByTestId('update-install'));
    expect(await screen.findByText(/changed on disk after it was checked/)).toBeInTheDocument();
  });
});

describe('when something fails', () => {
  it('a failed check is a sentence with a way to try again', async () => {
    const failed = { ...base, error: 'Zaram could not reach GitHub to list the releases. Check the connection and try again.' };
    fetchUpdateStatus.mockResolvedValue(failed);
    checkForUpdates.mockResolvedValue(failed);
    render(<UpdateBanner />);
    expect(await screen.findByTestId('update-error')).toHaveTextContent(/could not reach GitHub/);
    checkForUpdates.mockResolvedValue(available);
    await userEvent.click(screen.getByTestId('update-retry'));
    expect(checkForUpdates).toHaveBeenLastCalledWith(true);
    expect(await screen.findByTestId('update-available')).toBeInTheDocument();
  });

  it('a backend that cannot be reached shows nothing rather than a broken card', async () => {
    fetchUpdateStatus.mockRejectedValue(new Error('down'));
    render(<UpdateBanner />);
    await waitFor(() => expect(fetchUpdateStatus).toHaveBeenCalled());
    expect(screen.queryByTestId('update-banner')).toBeNull();
  });
});
