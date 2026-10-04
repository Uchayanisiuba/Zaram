/**
 * The model servers on this machine, and whether Zaram can reach them.
 *
 * Asked for 4 October 2026, the day a started TabbyAPI showed no Qwen: *"confirm we
 * have access to Ollama and Tabby in the section of Settings where users download
 * LLMs."* These assert the three facts the component keeps apart — installed,
 * running, and *picked up by Zaram* — because the useful failures are in the gaps
 * between them, and a single green dot would hide every one.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe as suite, expect, it, vi } from 'vitest';

import type { ModelServer } from '@/services/settingsClient';

const fetchModelServers = vi.fn();
const startModelServer = vi.fn();
const updateModelServer = vi.fn();

vi.mock('@/services/settingsClient', async () => {
  const actual = await vi.importActual<typeof import('@/services/settingsClient')>('@/services/settingsClient');
  return {
    ...actual,
    fetchModelServers: () => fetchModelServers(),
    startModelServer: (id: string) => startModelServer(id),
    updateModelServer: (id: string, update: unknown) => updateModelServer(id, update),
  };
});

import { SettingsError } from '@/services/settingsClient';
import ModelServers, { accessNote, describe } from './ModelServers';

function server(over: Partial<ModelServer> = {}): ModelServer {
  return {
    id: 'ollama',
    label: 'Ollama',
    port: 11434,
    state: 'running',
    installed: true,
    path: 'C:\\Ollama\\ollama.exe',
    modelCount: 3,
    models: ['gemma4:12b', 'qwen3-14b-16k:latest', 'bge-m3:latest'],
    canStart: false,
    problem: '',
    autoStart: true,
    fields: ['path'],
    failure: '',
    logPath: '',
    zaramSees: 3,
    ...over,
  };
}

function tabby(over: Partial<ModelServer> = {}): ModelServer {
  return server({
    id: 'tabbyapi',
    label: 'TabbyAPI',
    port: 1234,
    path: 'C:\\Users\\u\\tabbyAPI',
    modelCount: 1,
    models: ['Big-27B'],
    fields: ['path', 'python'],
    zaramSees: 1,
    ...over,
  });
}

beforeEach(() => {
  fetchModelServers.mockReset().mockResolvedValue([server(), tabby()]);
  startModelServer.mockReset();
  updateModelServer.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

async function loaded() {
  render(<ModelServers />);
  await screen.findByTestId('model-server-ollama');
}

suite('what is said beside the name', () => {
  it('says running with a model count', () => {
    expect(describe(server({ modelCount: 3 }))).toBe('running · 3 models');
    expect(describe(server({ modelCount: 1 }))).toBe('running · 1 model');
  });

  it.each([
    ['stopped', 'installed, not running'],
    ['not_installed', 'not installed'],
    ['cannot_start', 'installed, cannot be started'],
    ['stalled', 'not responding'],
    ['starting', 'starting…'],
  ] as const)('says %s in plain words', (state, words) => {
    expect(describe(server({ state }))).toBe(words);
  });

  it('names the port when something else is using it', () => {
    expect(describe(tabby({ state: 'port_taken' }))).toBe('port 1234 is used by another program');
  });
});

suite('whether Zaram can use what a server holds', () => {
  it('is only said about a server that is up', () => {
    expect(accessNote(server({ state: 'stopped' }))).toBeNull();
    expect(accessNote(server({ state: 'starting' }))).toBeNull();
  });

  it('makes no claim when the catalogue could not be asked', () => {
    /** `null` is *not asked*, which is not zero. Saying "Zaram has none" because
     *  the answer was missing would be a confident false statement. */
    expect(accessNote(server({ zaramSees: null }))).toBeNull();
  });

  it('warns when the server is up and Zaram holds none of its models', () => {
    /** **The case that started this.** A started TabbyAPI listing a Qwen that
     *  Zaram had not picked up, because Zaram probes at boot and on a rescan. */
    const note = accessNote(server({ modelCount: 1, zaramSees: 0 }));
    expect(note?.warn).toBe(true);
    expect(note?.text).toMatch(/not picked these up yet/);
  });

  it('does not warn about a partial count', () => {
    /** Some of what a server lists is not something Zaram offers — an embedding
     *  model, say — so 2 of 3 is ordinary and alarming about it would cry wolf. */
    const note = accessNote(server({ modelCount: 3, zaramSees: 2 }));
    expect(note?.warn).toBe(false);
  });

  it('says plainly when Zaram has them', () => {
    expect(accessNote(server({ modelCount: 3, zaramSees: 3 }))?.text).toMatch(/Zaram has them/);
  });

  it('does not call an empty server a problem', () => {
    /** TabbyAPI with its model not loaded yet lists nothing. That is a fact about
     *  the server, not a failure to be warned about. */
    const note = accessNote(tabby({ modelCount: 0, models: [], zaramSees: 0 }));
    expect(note?.warn).toBe(false);
    expect(note?.text).toMatch(/Nothing is loaded/);
  });
});

suite('the rows', () => {
  it('shows both servers, running, and how many are up', async () => {
    await loaded();
    expect(screen.getByTestId('model-server-state-ollama')).toHaveTextContent('running · 3 models');
    expect(screen.getByTestId('model-server-state-tabbyapi')).toHaveTextContent('running · 1 model');
    expect(screen.getByTestId('model-servers')).toHaveTextContent('2 of 2 running');
  });

  it('names the models each server holds', async () => {
    await loaded();
    expect(screen.getByTestId('model-server-tabbyapi')).toHaveTextContent('Big-27B');
    expect(screen.getByTestId('model-server-ollama')).toHaveTextContent('gemma4:12b');
  });

  it('counts a server that is only installed as not running', async () => {
    fetchModelServers.mockResolvedValue([server(), tabby({ state: 'stopped', canStart: true, modelCount: 0, models: [] })]);
    await loaded();
    expect(screen.getByTestId('model-servers')).toHaveTextContent('1 of 2 running');
  });

  it('shows a count beyond the names it lists', async () => {
    fetchModelServers.mockResolvedValue([server({ modelCount: 9, models: ['a', 'b', 'c'] })]);
    await loaded();
    expect(screen.getByTestId('model-server-ollama')).toHaveTextContent('+6');
  });

  it('shows the reason on a server that cannot be started', async () => {
    fetchModelServers.mockResolvedValue([
      tabby({ state: 'cannot_start', problem: 'Zaram could not find the Python environment it runs in.', canStart: false }),
    ]);
    render(<ModelServers />);
    expect(await screen.findByText(/Python environment it runs in/)).toBeTruthy();
    expect(screen.queryByTestId('start-tabbyapi')).toBeNull();
  });

  it('shows the end of the log when a launch failed', async () => {
    fetchModelServers.mockResolvedValue([
      tabby({ state: 'stopped', canStart: true, failure: "ModuleNotFoundError: No module named 'exllamav3'" }),
    ]);
    render(<ModelServers />);
    expect(await screen.findByTestId('model-server-failure-tabbyapi')).toHaveTextContent('exllamav3');
  });

  it('says so, and offers no start, when a server is not installed', async () => {
    fetchModelServers.mockResolvedValue([
      tabby({ state: 'not_installed', installed: false, path: null, canStart: false, modelCount: 0, models: [] }),
    ]);
    render(<ModelServers />);
    await screen.findByTestId('model-server-tabbyapi');
    expect(screen.getByTestId('model-server-tabbyapi')).toHaveTextContent('Not found where Zaram looks');
    expect(screen.queryByTestId('start-tabbyapi')).toBeNull();
    // Nothing to start automatically, so no switch about it.
    expect(screen.queryByTestId('auto-start-tabbyapi')).toBeNull();
  });
});

suite('starting a stopped server', () => {
  const stopped = () => tabby({ state: 'stopped', canStart: true, modelCount: 0, models: [], zaramSees: 0 });

  it('offers Start only for a server that can be started', async () => {
    fetchModelServers.mockResolvedValue([server(), stopped()]);
    await loaded();
    expect(screen.queryByTestId('start-ollama')).toBeNull();
    expect(screen.getByTestId('start-tabbyapi')).toHaveTextContent('Start TabbyAPI');
  });

  it('starts it and shows that it is on its way', async () => {
    fetchModelServers.mockResolvedValue([server(), stopped()]);
    startModelServer.mockResolvedValue(tabby({ state: 'starting', canStart: false, modelCount: 0, models: [] }));
    await loaded();
    fireEvent.click(screen.getByTestId('start-tabbyapi'));
    await waitFor(() => expect(startModelServer).toHaveBeenCalledWith('tabbyapi'));
    await waitFor(() =>
      expect(screen.getByTestId('model-server-state-tabbyapi')).toHaveTextContent('starting…'),
    );
    expect(screen.queryByTestId('start-tabbyapi')).toBeNull();
  });

  it('says why when it could not', async () => {
    fetchModelServers.mockResolvedValue([server(), stopped()]);
    startModelServer.mockRejectedValue(new SettingsError('Something other than TabbyAPI is already using port 1234.', 409));
    await loaded();
    fireEvent.click(screen.getByTestId('start-tabbyapi'));
    expect(await screen.findByTestId('model-servers-error')).toHaveTextContent('already using port 1234');
  });

  it('keeps looking while it starts, and stops once it is up', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: false });
    fetchModelServers
      .mockResolvedValueOnce([tabby({ state: 'starting', canStart: false, modelCount: 0, models: [] })])
      .mockResolvedValueOnce([tabby({ state: 'starting', canStart: false, modelCount: 0, models: [] })])
      .mockResolvedValue([tabby()]);

    render(<ModelServers />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(fetchModelServers).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });
    expect(fetchModelServers).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100);
    });
    expect(fetchModelServers).toHaveBeenCalledTimes(3);
    expect(screen.getByTestId('model-server-state-tabbyapi')).toHaveTextContent('running · 1 model');

    // Up, so it stops asking — polling a running server forever is a leak.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(fetchModelServers).toHaveBeenCalledTimes(3);
  });

  it('does not poll at all when nothing is starting', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: false });
    render(<ModelServers />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(fetchModelServers).toHaveBeenCalledTimes(1);
  });
});

suite('a server that is up and not picked up', () => {
  it('says so and offers to look again', async () => {
    const onRescan = vi.fn();
    fetchModelServers.mockResolvedValue([tabby({ zaramSees: 0, modelCount: 1 })]);
    render(<ModelServers onRescan={onRescan} />);
    await screen.findByTestId('model-server-tabbyapi');
    expect(screen.getByTestId('model-server-access-tabbyapi')).toHaveTextContent('not picked these up yet');
    fireEvent.click(screen.getByTestId('rescan-tabbyapi'));
    expect(onRescan).toHaveBeenCalledTimes(1);
  });

  it('offers no rescan when Zaram already has the models', async () => {
    render(<ModelServers onRescan={vi.fn()} />);
    await screen.findByTestId('model-server-tabbyapi');
    expect(screen.queryByTestId('rescan-tabbyapi')).toBeNull();
  });

  it('offers no rescan where there is nothing to rescan with', async () => {
    fetchModelServers.mockResolvedValue([tabby({ zaramSees: 0, modelCount: 1 })]);
    render(<ModelServers />);
    await screen.findByTestId('model-server-tabbyapi');
    expect(screen.queryByTestId('rescan-tabbyapi')).toBeNull();
  });
});

suite('starting with Zaram', () => {
  it('shows the switch as on by default', async () => {
    await loaded();
    expect(screen.getByTestId('auto-start-tabbyapi')).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByTestId('auto-start-tabbyapi')).toHaveTextContent('Starts with Zaram');
  });

  it('turns it off', async () => {
    updateModelServer.mockResolvedValue(tabby({ autoStart: false }));
    await loaded();
    fireEvent.click(screen.getByTestId('auto-start-tabbyapi'));
    await waitFor(() => expect(updateModelServer).toHaveBeenCalledWith('tabbyapi', { autoStart: false }));
    await waitFor(() =>
      expect(screen.getByTestId('auto-start-tabbyapi')).toHaveAttribute('aria-checked', 'false'),
    );
    expect(screen.getByTestId('auto-start-tabbyapi')).toHaveTextContent('Does not start with Zaram');
  });
});

suite('saying where a server is installed', () => {
  it('asks for a path under Ollama and a path and a Python under TabbyAPI', async () => {
    /** A Python field under Ollama — one executable — would settle nothing. The
     *  backend says which settings mean something; the component draws only those. */
    await loaded();
    expect(screen.getByTestId('path-ollama')).toBeTruthy();
    expect(screen.queryByTestId('python-ollama')).toBeNull();
    expect(screen.getByTestId('path-tabbyapi')).toBeTruthy();
    expect(screen.getByTestId('python-tabbyapi')).toBeTruthy();
  });

  it('shows where it was found', async () => {
    await loaded();
    expect(screen.getByTestId('path-tabbyapi')).toHaveValue('C:\\Users\\u\\tabbyAPI');
  });

  it('offers Save only once something has been typed', async () => {
    await loaded();
    expect(screen.queryByTestId('save-location-tabbyapi')).toBeNull();
    await userEvent.type(screen.getByTestId('path-tabbyapi'), 'x');
    expect(screen.getByTestId('save-location-tabbyapi')).toBeTruthy();
  });

  it('saves the path that was typed, and nothing it was not asked to change', async () => {
    updateModelServer.mockResolvedValue(tabby({ path: 'D:\\tabby' }));
    await loaded();
    const field = screen.getByTestId('path-tabbyapi');
    await userEvent.clear(field);
    await userEvent.type(field, 'D:\\tabby');
    fireEvent.click(screen.getByTestId('save-location-tabbyapi'));
    await waitFor(() => expect(updateModelServer).toHaveBeenCalledWith('tabbyapi', { path: 'D:\\tabby' }));
  });

  it('shows the refusal against the field it is about', async () => {
    /** The backend refuses a folder that is not a TabbyAPI checkout, with the
     *  reason. It belongs under the field, not in a banner above everything. */
    updateModelServer.mockRejectedValue(
      new SettingsError('That folder does not look like a TabbyAPI checkout.', 400),
    );
    await loaded();
    await userEvent.type(screen.getByTestId('path-tabbyapi'), 'x');
    fireEvent.click(screen.getByTestId('save-location-tabbyapi'));
    expect(await screen.findByTestId('location-problem-tabbyapi')).toHaveTextContent('does not look like');
    expect(screen.queryByTestId('model-servers-error')).toBeNull();
  });
});

suite('when the status cannot be read', () => {
  it('says so rather than showing an empty list that reads as no servers', async () => {
    fetchModelServers.mockRejectedValue(new SettingsError('Backend unreachable', 503));
    render(<ModelServers />);
    expect(await screen.findByTestId('model-servers-error')).toHaveTextContent('Backend unreachable');
    expect(screen.queryByTestId('model-server-ollama')).toBeNull();
  });
});
