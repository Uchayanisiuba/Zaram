/**
 * The routing chip: where questions go, and which model answers.
 *
 * Both decisions used to live in Settings, so keeping the next question on
 * this machine cost a trip out of the conversation and back. This is that
 * decision moved to where it is made.
 *
 * The assertions a friendlier version would drop:
 *
 * * **Discovery never rides on a render.** `fetchModels` asks every connected
 *   cloud provider what it offers, so it is egress. This control renders in
 *   every conversation; if the list were fetched on mount, opening an old chat
 *   would call out to every provider.
 * * **Every installed chat model is offered, including ones Zaram would not
 *   pick itself.** `selectable_by_default` gates auto-routing, not the user
 *   asking. Hiding a model someone deliberately installed, with no
 *   explanation, is the silent-failure pattern.
 * * **Embedders are never offered**, because Ollama answers `/api/generate`
 *   for `bge-m3` with a 400 — a choice that can only fail.
 * * **The two cloud-unavailable causes are named apart.** "No provider
 *   connected" and "nothing may leave yet" are different problems with
 *   different fixes, and collapsing them sends someone to fix nothing.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const fetchModels = vi.fn();
const fetchRoutingSettings = vi.fn();
const updateRoutingSettings = vi.fn();

vi.mock('@/services/settingsClient', () => ({
  fetchModels: (...a: unknown[]) => fetchModels(...a),
  fetchRoutingSettings: (...a: unknown[]) => fetchRoutingSettings(...a),
  updateRoutingSettings: (...a: unknown[]) => updateRoutingSettings(...a),
}));

vi.mock('@/components/settings/AdvancedModelField', () => ({
  describeDataPolicy: (p: string | null) =>
    p === 'logged_and_trained_on' ? 'logged and trained on' : 'terms unknown',
}));

let canLeaveDevice = true;
let providers: { id: string; locality: string }[] = [];

vi.mock('@/stores/systemStore', () => ({
  useSystemStore: (selector: (s: unknown) => unknown) =>
    selector({ routing: { canLeaveDevice, providers } }),
  cloudModelConnected: (routing: { providers?: { locality: string }[] } | null) =>
    (routing?.providers ?? []).some((p) => p.locality && p.locality !== 'local'),
}));

import RoutingControl from './RoutingControl';

const model = (over: Partial<Record<string, unknown>>) => ({
  id: 'x',
  displayName: 'x',
  provider: 'ollama',
  locality: 'local',
  dataPolicy: null,
  selectableByDefault: true,
  fitsResident: true,
  residentBudgetBytes: 9_100_000_000,
  sizeBytes: 4_700_000_000,
  category: 'llm',
  ...over,
});

const MODELS = [
  model({ id: 'ollama:qwen', displayName: 'qwen2.5:7b' }),
  model({
    id: 'ollama:gemma4',
    displayName: 'gemma4:26b',
    fitsResident: false,
    sizeBytes: 18_200_000_000,
  }),
  model({ id: 'ollama:bge', displayName: 'bge-m3', category: 'embedding' }),
  model({
    id: 'openrouter:free',
    displayName: 'some-free-model',
    provider: 'openrouter',
    locality: 'cloud',
    dataPolicy: 'logged_and_trained_on',
    // Zaram will not auto-route here. The user may still choose it.
    selectableByDefault: false,
    fitsResident: null,
    sizeBytes: null,
  }),
];

beforeEach(() => {
  canLeaveDevice = true;
  providers = [
    { id: 'ollama', locality: 'local' },
    { id: 'openrouter', locality: 'cloud' },
  ];
  fetchModels.mockResolvedValue(MODELS);
  fetchRoutingSettings.mockResolvedValue({ routingPreference: 'auto', defaultModel: null });
  updateRoutingSettings.mockImplementation(
    async (u: { routingPreference?: string; defaultModel?: string }) => ({
      routingPreference: u.routingPreference ?? 'auto',
      defaultModel: u.defaultModel ? u.defaultModel : null,
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

async function openPanel() {
  render(<RoutingControl />);
  const chip = await screen.findByTestId('routing-chip');
  await userEvent.click(chip);
  return screen.findByTestId('routing-panel');
}

describe('before anything is known', () => {
  it('says it is checking rather than showing a mode it has not read', () => {
    fetchRoutingSettings.mockReturnValue(new Promise(() => {}));

    render(<RoutingControl />);

    expect(screen.getByText(/checking routing/i)).toBeTruthy();
    expect(screen.queryByTestId('routing-chip')).toBeNull();
  });

  it('says so when the preference cannot be read', async () => {
    fetchRoutingSettings.mockRejectedValue(new Error('offline'));

    render(<RoutingControl />);

    await waitFor(() => expect(screen.getByText(/routing unavailable/i)).toBeTruthy());
  });
});

describe('discovery is a deliberate act', () => {
  it('does not touch the network until the chip is pressed', async () => {
    render(<RoutingControl />);
    await screen.findByTestId('routing-chip');

    expect(fetchModels).not.toHaveBeenCalled();

    await userEvent.click(screen.getByTestId('routing-chip'));

    await waitFor(() => expect(fetchModels).toHaveBeenCalledTimes(1));
  });
});

describe('the lists', () => {
  it('separates what runs here from what leaves', async () => {
    const panel = await openPanel();

    await waitFor(() => expect(within(panel).getByText('qwen2.5:7b')).toBeTruthy());
    expect(within(panel).getByText(/on this machine/i)).toBeTruthy();
    expect(within(panel).getByText('some-free-model')).toBeTruthy();
  });

  it('never offers an embedder', async () => {
    const panel = await openPanel();

    await waitFor(() => expect(within(panel).getByText('qwen2.5:7b')).toBeTruthy());
    // Ollama answers `/api/generate` for it with a 400.
    expect(within(panel).queryByText('bge-m3')).toBeNull();
  });

  it('offers a model Zaram would not auto-route to', async () => {
    const panel = await openPanel();

    // `selectable_by_default: false` stops Zaram choosing it unasked. It does
    // not stop the user choosing it, and hiding it would be unexplained.
    await waitFor(() => expect(within(panel).getByText('some-free-model')).toBeTruthy());
    expect(within(panel).getByText(/logged and trained on/i)).toBeTruthy();
  });

  it('names the cost in numbers for a model that will be slow', async () => {
    const panel = await openPanel();

    // "Does not fit" is a verdict. This is something a person can act on.
    await waitFor(() =>
      expect(within(panel).getByText(/18\.2 GB against 9\.1 GB of VRAM/i)).toBeTruthy(),
    );
  });

  it('keeps the data policy to the list where it is the question', async () => {
    const panel = await openPanel();
    await waitFor(() => expect(within(panel).getByText('qwen2.5:7b')).toBeTruthy());

    // One cloud model, one policy line — not one against every local model too.
    expect(within(panel).queryAllByText(/logged and trained on|terms unknown/i)).toHaveLength(1);
  });
});

describe('choosing', () => {
  it('pins the model the user picked', async () => {
    const panel = await openPanel();
    await waitFor(() => expect(within(panel).getByText('qwen2.5:7b')).toBeTruthy());

    await userEvent.click(within(panel).getByText('qwen2.5:7b'));

    await waitFor(() =>
      expect(updateRoutingSettings).toHaveBeenCalledWith({ defaultModel: 'qwen2.5:7b' }),
    );
  });

  it('hands the choice back when the pinned model is pressed again', async () => {
    fetchRoutingSettings.mockResolvedValue({
      routingPreference: 'auto',
      defaultModel: 'qwen2.5:7b',
    });
    const panel = await openPanel();
    await waitFor(() => expect(within(panel).getByText('qwen2.5:7b')).toBeTruthy());

    await userEvent.click(within(panel).getByText('qwen2.5:7b'));

    // `''` is what the client documents as "let Zaram decide" — distinct from
    // `undefined`, which leaves the field alone.
    await waitFor(() =>
      expect(updateRoutingSettings).toHaveBeenCalledWith({ defaultModel: '' }),
    );
  });

  it('changes where questions may go', async () => {
    const panel = await openPanel();

    await userEvent.click(within(panel).getByRole('button', { name: 'Prefer local' }));

    await waitFor(() =>
      expect(updateRoutingSettings).toHaveBeenCalledWith({ routingPreference: 'prefer_local' }),
    );
  });

  it('puts everything back when the save fails', async () => {
    const panel = await openPanel();
    updateRoutingSettings.mockRejectedValue(new Error('refused'));

    await userEvent.click(within(panel).getByRole('button', { name: 'Prefer local' }));

    await waitFor(() => expect(screen.getByText(/not saved/i)).toBeTruthy());
    // Not left reading "Prefer local", which would tell someone their next
    // question stays here when nothing was saved.
    expect(screen.getByTestId('routing-chip').textContent).toContain('Auto');
  });
});

describe('the chip itself', () => {
  it('claims the guarantee only for prefer_local', async () => {
    fetchRoutingSettings.mockResolvedValue({
      routingPreference: 'prefer_local',
      defaultModel: null,
    });

    render(<RoutingControl />);

    await waitFor(() => expect(screen.getByText(/stays on this machine/i)).toBeTruthy());
  });

  it('names the pinned model rather than hiding it', async () => {
    fetchRoutingSettings.mockResolvedValue({
      routingPreference: 'auto',
      defaultModel: 'qwen2.5:7b',
    });

    render(<RoutingControl />);

    // "Never hide the model" — and a chip that said only "Auto" while a pin
    // was in force would be lying about what is going to answer.
    await waitFor(() =>
      expect(screen.getByTestId('routing-chip').textContent).toContain('qwen2.5:7b'),
    );
  });
});

describe('when cloud cannot be reached, it says which reason', () => {
  it('distinguishes a closed gate from a missing provider', async () => {
    canLeaveDevice = false;

    const panel = await openPanel();
    const cloudButton = within(panel).getByRole('button', { name: 'Prefer cloud' });

    expect((cloudButton as HTMLButtonElement).disabled).toBe(true);
    expect(cloudButton.getAttribute('title')).toMatch(/nothing may leave/i);
  });

  it('says no provider when there genuinely is none', async () => {
    canLeaveDevice = false;
    providers = [{ id: 'ollama', locality: 'local' }];

    const panel = await openPanel();
    const cloudButton = within(panel).getByRole('button', { name: 'Prefer cloud' });

    expect((cloudButton as HTMLButtonElement).disabled).toBe(true);
    expect(cloudButton.getAttribute('title')).toMatch(/no cloud provider is connected/i);
  });

  it('leaves it alone when cloud is genuinely usable', async () => {
    const panel = await openPanel();
    const cloudButton = within(panel).getByRole('button', { name: 'Prefer cloud' });

    expect((cloudButton as HTMLButtonElement).disabled).toBe(false);
  });
});
