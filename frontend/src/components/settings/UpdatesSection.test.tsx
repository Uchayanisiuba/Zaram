/**
 * The Settings side of updates: the switch is rule 7g's answer, changeable, and the
 * controls are the banner's, from the same store.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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

import UpdatesSection from './UpdatesSection';
import { resetUpdateStoreForTests } from '@/stores/updateStore';

function Row({ label, value, detail, children }: { label: string; value?: string; detail?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div data-testid={`row-${label}`}>
      <span>{label}</span> <span>{value}</span>
      <div>{detail}</div>
      {children}
    </div>
  );
}

const release = {
  tag: 'v0.1.0-alpha.8',
  page: 'https://github.com/Uchayanisiuba/Zaram/releases/tag/v0.1.0-alpha.8',
  installer: { name: 'Zaram-0.1.0-x64.exe', url: 'https://github.com/x', size: 208539009 },
};
const base: UpdateStatus = {
  current: 'v0.1.0-alpha.7', known: true, checks: true, last_checked: 1, phase: 'up_to_date', latest: null,
  progress: { done: 0, total: 0 }, error: '', ready: false, can_install: true, manual_reason: '',
  release_page: 'https://github.com/Uchayanisiuba/Zaram/releases',
};

beforeEach(() => {
  vi.clearAllMocks();
  resetUpdateStoreForTests();
  checkForUpdates.mockImplementation(async () => base);
});

describe('Settings → Updates', () => {
  it('says which release this is, and what a check sends', async () => {
    fetchUpdateStatus.mockResolvedValue(base);
    render(<UpdatesSection Row={Row} />);
    expect(await screen.findByText('up to date')).toBeInTheDocument();
    const text = document.body.textContent ?? '';
    expect(text).toMatch(/This is v0\.1\.0-alpha\.7/);
    expect(text).toMatch(/list of releases/i);
    expect(text).toMatch(/no version, no identifier/i);
    expect(text).toMatch(/SHA-256/);
    expect(text).toMatch(/nothing is installed until you press/i);
  });

  it('a development build says it cannot tell, and offers no control', async () => {
    fetchUpdateStatus.mockResolvedValue({ ...base, current: null, known: false });
    render(<UpdatesSection Row={Row} />);
    expect(await screen.findByText('not available')).toBeInTheDocument();
    expect(screen.queryByTestId('update-check-now')).toBeNull();
    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('the switch shows the answer and changing it records the new one', async () => {
    fetchUpdateStatus.mockResolvedValue(base);
    setUpdateChecks.mockResolvedValue({ ...base, checks: false });
    render(<UpdatesSection Row={Row} />);
    const box = (await screen.findByTestId('update-checks-switch')) as HTMLInputElement;
    expect(box.checked).toBe(true);
    await userEvent.click(box);
    await waitFor(() => expect(setUpdateChecks).toHaveBeenCalledWith(false));
    expect(checkForUpdates).not.toHaveBeenCalledWith(true);
  });

  it('an unanswered question shows the switch off', async () => {
    fetchUpdateStatus.mockResolvedValue({ ...base, checks: null });
    render(<UpdatesSection Row={Row} />);
    expect(((await screen.findByTestId('update-checks-switch')) as HTMLInputElement).checked).toBe(false);
  });

  it('Check now is an act, forced', async () => {
    fetchUpdateStatus.mockResolvedValue({ ...base, checks: false });
    render(<UpdatesSection Row={Row} />);
    await userEvent.click(await screen.findByTestId('update-check-now'));
    expect(checkForUpdates).toHaveBeenCalledWith(true);
  });

  it('a newer build is named, with the size on the Download button', async () => {
    const available = { ...base, phase: 'available' as const, latest: release };
    fetchUpdateStatus.mockResolvedValue(available);
    checkForUpdates.mockResolvedValue(available);
    startUpdateDownload.mockResolvedValue({ ...available, phase: 'downloading' as const });
    render(<UpdatesSection Row={Row} />);
    expect(await screen.findByText('v0.1.0-alpha.8 available')).toBeInTheDocument();
    await userEvent.click(screen.getByTestId('update-download'));
    // Once it is under way the button goes and the row says so.
    expect(await screen.findByText('downloading')).toBeInTheDocument();
    expect(screen.queryByTestId('update-download')).toBeNull();
    expect(startUpdateDownload).toHaveBeenCalledTimes(1);
  });

  it('ready to run offers Restart and install, and only that press runs it', async () => {
    const ready = { ...base, phase: 'ready' as const, ready: true, latest: release };
    fetchUpdateStatus.mockResolvedValue(ready);
    checkForUpdates.mockResolvedValue(ready);
    installUpdate.mockResolvedValue({ ok: true });
    render(<UpdatesSection Row={Row} />);
    const button = await screen.findByTestId('update-install');
    expect(installUpdate).not.toHaveBeenCalled();
    await userEvent.click(button);
    expect(installUpdate).toHaveBeenCalledTimes(1);
  });

  it('where it cannot install, it says why and offers the release page', async () => {
    const portable = {
      ...base, phase: 'available' as const, latest: release, can_install: false,
      manual_reason: 'This is the portable build, which cannot replace itself. Download the new one from the release page.',
    };
    fetchUpdateStatus.mockResolvedValue(portable);
    checkForUpdates.mockResolvedValue(portable);
    render(<UpdatesSection Row={Row} />);
    await userEvent.click(await screen.findByTestId('update-page'));
    expect(openInBrowser).toHaveBeenCalledWith(release.page);
    expect(document.body.textContent).toMatch(/portable build/);
    expect(screen.queryByTestId('update-download')).toBeNull();
  });
});
