/**
 * The Computer Use section says what the driver itself reports.
 *
 * 10 October 2026: it read `server.cuaHealth`, a field nothing ever filled in, so an
 * installed driver said "Health check not available" forever and "Check health" only
 * re-read the list. It now asks `/tools/cua-driver/health` for every listed driver.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const fetchServers = vi.fn();
const fetchCuaHealth = vi.fn();
const installCuaDriver = vi.fn();
const setServerEnabled = vi.fn();

vi.mock('../../services/toolsClient', () => ({
  fetchServers: () => fetchServers(),
  fetchServerTools: vi.fn().mockResolvedValue([]),
  pinTools: vi.fn(),
  installCuaDriver: (v: string) => installCuaDriver(v),
  fetchCuaHealth: (id: string) => fetchCuaHealth(id),
  setServerEnabled: (id: string, on: boolean) => setServerEnabled(id, on),
}));
vi.mock('./ComputerUseActions', () => ({ ComputerUseAction: () => null }));
vi.mock('@/lib/openInBrowser', () => ({ openInBrowser: vi.fn() }));

import ComputerUseSection from './ComputerUseSection';

function Row({ label, value, detail, children }: { label: string; value?: string; detail?: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div data-testid={`row-${label}`}>
      <span>{label}</span> <span>{value}</span>
      <div>{detail}</div>
      {children}
    </div>
  );
}

const driver = {
  id: 'cua-driver',
  command: ['C:\data\bin\cua-driver.exe', 'mcp'],
  url: '',
  transport: 'stdio',
  reachable: true,
  writes: 'host_undo',
  grantedTools: [],
  knownHost: null,
  tools: null,
  offered: null,
  toolBudget: null,
  builtin: false,
  pinnedTools: [],
  enabled: true,
};

beforeEach(() => {
  fetchServers.mockReset();
  fetchCuaHealth.mockReset();
  installCuaDriver.mockReset();
  setServerEnabled.mockReset().mockResolvedValue(undefined);
});

describe('an installed driver', () => {
  it('says what the driver reported about itself, without a button being pressed', async () => {
    fetchServers.mockResolvedValue([driver]);
    fetchCuaHealth.mockResolvedValue({ status: 'healthy', version: '0.34.1', platform: 'win32' });
    render(<ComputerUseSection Row={Row} />);
    expect(await screen.findByText(/Ready \(cua-driver 0\.34\.1\)/)).toBeInTheDocument();
    expect(fetchCuaHealth).toHaveBeenCalledWith('cua-driver');
    expect(screen.queryByText(/Health check not available/)).toBeNull();
  });

  it('asks again when Check health is pressed', async () => {
    fetchServers.mockResolvedValue([driver]);
    fetchCuaHealth.mockResolvedValue({ status: 'error', error: 'UIAutomation is not reachable' });
    render(<ComputerUseSection Row={Row} />);
    expect(await screen.findByText('UIAutomation is not reachable')).toBeInTheDocument();
    fetchCuaHealth.mockResolvedValue({ status: 'healthy', version: '0.34.1' });
    await userEvent.setup().click(screen.getByText('Check health'));
    await waitFor(() => expect(screen.getByText(/Ready/)).toBeInTheDocument());
  });
});

describe('before it is installed', () => {
  it('says the download is the permission, what it costs, and that it will be connected', async () => {
    fetchServers.mockResolvedValue([]);
    render(<ComputerUseSection Row={Row} />);
    const text = await screen.findByText(/Downloads cua-driver 0\.34\.1/);
    expect(text).toHaveTextContent('about 30 MB');
    expect(text).toHaveTextContent('telemetry switched off');
    expect(text).not.toHaveTextContent('does not start it');
  });

  it('lists the driver once the install reports it connected', async () => {
    fetchServers.mockResolvedValueOnce([]).mockResolvedValue([driver]);
    fetchCuaHealth.mockResolvedValue({ status: 'healthy', version: '0.34.1' });
    installCuaDriver.mockResolvedValue({ status: 'complete', progress: 1, message: 'connected', error: '' });
    render(<ComputerUseSection Row={Row} />);
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Install cua-driver' }));
    expect(await screen.findByText(/Ready/)).toBeInTheDocument();
    expect(installCuaDriver).toHaveBeenCalledWith('latest');
  });
});


describe('the on/off switch', () => {
  it('switches it off, and the row then says it is off and asks the driver nothing', async () => {
    fetchServers.mockResolvedValueOnce([driver]).mockResolvedValue([{ ...driver, enabled: false }]);
    fetchCuaHealth.mockResolvedValue({ status: 'healthy', version: '0.34.1' });
    render(<ComputerUseSection Row={Row} />);
    await screen.findByText(/Ready/);
    fetchCuaHealth.mockClear();
    await userEvent.setup().click(screen.getByTestId('computer-use-off-cua-driver'));
    expect(setServerEnabled).toHaveBeenCalledWith('cua-driver', false);
    expect(await screen.findByText(/Switched off\. Zaram offers the model none of its tools/)).toBeInTheDocument();
    expect(screen.getByTestId('computer-use-off-cua-driver')).toHaveAttribute('aria-pressed', 'true');
    expect(fetchCuaHealth).not.toHaveBeenCalled();
    expect(screen.queryByText('Check health')).toBeNull();
  });

  it('switches it back on and asks the driver how it is', async () => {
    fetchServers.mockResolvedValueOnce([{ ...driver, enabled: false }]).mockResolvedValue([driver]);
    fetchCuaHealth.mockResolvedValue({ status: 'healthy', version: '0.34.1' });
    render(<ComputerUseSection Row={Row} />);
    await screen.findByText(/Switched off/);
    expect(fetchCuaHealth).not.toHaveBeenCalled();
    await userEvent.setup().click(screen.getByTestId('computer-use-on-cua-driver'));
    expect(setServerEnabled).toHaveBeenCalledWith('cua-driver', true);
    expect(await screen.findByText(/Ready/)).toBeInTheDocument();
  });
});
