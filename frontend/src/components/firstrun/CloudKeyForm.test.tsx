/**
 * What the first-run key form must not say, and what it must.
 *
 * This is the screen where someone hands Zaram a credential for a third party,
 * and it is seen once. Every rule below is one a friendlier version of this
 * component would break by accident — a reassuring "Connected!", a data policy
 * tucked behind a disclosure, a provider list that quietly hides the free tiers
 * because their terms are bad.
 */
import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import CloudKeyForm from './CloudKeyForm';

const catalogue = {
  generated: '2026-08-01',
  providers: [
    {
      id: 'openrouter',
      displayName: 'OpenRouter',
      baseUrl: 'https://openrouter.ai/api/v1',
      available: true,
      note: 'Free models here are logged by the provider and may be trained on.',
      keyUrl: 'https://openrouter.ai/keys',
      compatibility: 'openai',
      auth: 'bearer',
    },
    {
      id: 'lm_studio',
      displayName: 'LM Studio',
      baseUrl: 'http://127.0.0.1:1234/v1',
      available: true,
      note: 'Runs on this machine.',
      keyUrl: '',
      compatibility: 'openai',
      auth: 'none',
    },
    {
      id: 'not_yet',
      displayName: 'Something Unsupported',
      baseUrl: '',
      available: false,
      note: 'Zaram has no adapter for this one.',
      keyUrl: '',
      compatibility: '',
      auth: 'bearer',
    },
  ],
};

/** Typed to the real signature so a drift in either shows up as a tsc error
 *  rather than as a test that passes against a call nobody makes any more. */
type ConnectInput = { providerId?: string; baseUrl?: string; apiKey?: string };

const fetchProviderCatalogue = vi.fn(async () => catalogue);
const connectCloudProvider = vi.fn(async (_input: ConnectInput) => ({
  connections: [],
  configured: true,
  generated: '2026-08-01',
}));

vi.mock('@/services/settingsClient', () => ({
  fetchProviderCatalogue: () => fetchProviderCatalogue(),
  connectCloudProvider: (input: ConnectInput) => connectCloudProvider(input),
}));

afterEach(cleanup);
beforeEach(() => {
  fetchProviderCatalogue.mockClear();
  connectCloudProvider.mockClear();
});

async function choose(providerLabel: string) {
  const user = userEvent.setup();
  render(<CloudKeyForm onConnected={() => {}} />);
  const select = await screen.findByRole('combobox');
  await user.selectOptions(select, providerLabel);
  return user;
}

describe('choosing a provider', () => {
  it('offers only what a key can be pasted into', async () => {
    render(<CloudKeyForm onConnected={() => {}} />);

    await screen.findByRole('combobox');

    // A loopback server needs no key, and an unsupported entry has nowhere to
    // send one. Offering either asks for a credential with no destination.
    expect(screen.getByRole('option', { name: 'OpenRouter' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'LM Studio' })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Something Unsupported' })).not.toBeInTheDocument();
  });

  it('states the data policy while the user is choosing, not after', async () => {
    // `CLAUDE.md`: *"add a free Gemini key — your prompts train Google, and
    // Zaram will tell you every time one goes."* Being able to say this is the
    // product's whole position on free tiers, and it is worth nothing if it
    // appears only once the key is already stored.
    await choose('openrouter');

    expect(await screen.findByTestId('cloud-key-note')).toHaveTextContent(
      /logged by the provider and may be trained on/,
    );
  });

  it('does not hide a provider because its terms are bad', async () => {
    // `selectable_by_default` stops *Zaram* routing to a provider whose terms
    // are unknown. It must never stop a person choosing one knowingly — that
    // is the line between a consent gate and a paternalism gate.
    render(<CloudKeyForm onConnected={() => {}} />);

    expect(await screen.findByRole('option', { name: 'OpenRouter' })).toBeInTheDocument();
  });
});

describe('saving the key', () => {
  it('sends the chosen provider and the key, and nothing else', async () => {
    const user = await choose('openrouter');

    await user.type(screen.getByLabelText(/your key/i), 'sk-or-v1-not-a-real-key');
    await user.click(screen.getByRole('button', { name: /save key/i }));

    await waitFor(() => expect(connectCloudProvider).toHaveBeenCalledTimes(1));
    expect(connectCloudProvider).toHaveBeenCalledWith({
      providerId: 'openrouter',
      apiKey: 'sk-or-v1-not-a-real-key',
    });
  });

  it('never claims the key works', async () => {
    // The backend makes no network call, so a 200 means "configured" and
    // nothing else. A tick reading "Connected!" would be a claim this code
    // cannot support, and the user would find out it was wrong mid-question.
    const user = await choose('openrouter');

    await user.type(screen.getByLabelText(/your key/i), 'sk-test');
    await user.click(screen.getByRole('button', { name: /save key/i }));

    const saved = await screen.findByTestId('cloud-key-saved');

    expect(saved).toHaveTextContent(/has not contacted them/i);
    expect(saved.textContent).not.toMatch(/\b(connected|verified|valid|working)\b/i);
  });

  it('tells the caller so readiness can be asked again', async () => {
    // Without this the setup screen keeps standing over a product that has
    // just become able to answer.
    const onConnected = vi.fn();
    const user = userEvent.setup();
    render(<CloudKeyForm onConnected={onConnected} />);

    await user.selectOptions(await screen.findByRole('combobox'), 'openrouter');
    await user.type(screen.getByLabelText(/your key/i), 'sk-test');
    await user.click(screen.getByRole('button', { name: /save key/i }));

    await waitFor(() => expect(onConnected).toHaveBeenCalledTimes(1));
  });

  it('will not save without both a provider and a key', async () => {
    const user = userEvent.setup();
    render(<CloudKeyForm onConnected={() => {}} />);
    await screen.findByRole('combobox');

    const save = screen.getByRole('button', { name: /save key/i });
    expect(save).toBeDisabled();

    await user.type(screen.getByLabelText(/your key/i), 'sk-test');
    // A key with no provider has nowhere to go.
    expect(save).toBeDisabled();
  });

  it('surfaces a refusal in the provider’s own words', async () => {
    // The backend returns the catalogue's sentence so the user can tell "wrong
    // key" from "Zaram cannot speak to this provider at all". Replacing it
    // with a generic failure here would throw that away.
    connectCloudProvider.mockRejectedValueOnce(new Error('Zaram has no adapter for that.'));
    const user = await choose('openrouter');

    await user.type(screen.getByLabelText(/your key/i), 'sk-test');
    await user.click(screen.getByRole('button', { name: /save key/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Zaram has no adapter for that.');
  });

  it('does not leave the key in the form after saving', async () => {
    const user = await choose('openrouter');

    const field = screen.getByLabelText(/your key/i) as HTMLInputElement;
    await user.type(field, 'sk-test');
    await user.click(screen.getByRole('button', { name: /save key/i }));

    await screen.findByTestId('cloud-key-saved');
    expect(document.querySelector('input[type="password"]')).toBeNull();
  });
});

describe('when the manifest cannot be read', () => {
  it('says so rather than showing an empty picker', async () => {
    // Same posture as `useReadiness`: a failed probe is not a claim about the
    // world, and an empty dropdown reads as "no providers exist".
    fetchProviderCatalogue.mockRejectedValueOnce(new Error('nope'));
    render(<CloudKeyForm onConnected={() => {}} />);

    expect(await screen.findByText(/could not read its provider list/i)).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });
});

describe('the key field itself', () => {
  it('is a password field that browsers will not remember or spellcheck', async () => {
    render(<CloudKeyForm onConnected={() => {}} />);
    await screen.findByRole('combobox');

    const field = screen.getByLabelText(/your key/i);

    expect(field).toHaveAttribute('type', 'password');
    expect(field).toHaveAttribute('autocomplete', 'off');
    expect(field).toHaveAttribute('spellcheck', 'false');
  });
});
