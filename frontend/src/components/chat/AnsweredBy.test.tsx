/**
 * "Answered by X — ask another": the model switch, at the moment of doubt.
 *
 * A picker beside the input would ask someone to predict which model suits a
 * question they have not finished typing. Rule 7e says never to ask what the
 * system can answer from behaviour, and rule 7h says to offer at the moment of
 * doubt instead — which is here, under a reply that exists and can be judged.
 *
 * Three things are asserted that a friendlier version would drop:
 *
 * * **The model list is fetched on the press, never on render.** `fetchModels`
 *   asks every connected cloud provider what it offers, so it is egress. A
 *   reply re-renders whenever a conversation is reopened; if discovery rode
 *   along, reopening last week's chat would call out to every provider.
 * * **An embedder is never offered.** Ollama answers `/api/generate` for
 *   `bge-m3` with a 400, so offering it is offering a choice that can only
 *   fail — the defect the Settings picker already fixed once.
 * * **The data policy travels with the button**, because this is the moment
 *   someone chooses to send their question somewhere new.
 */
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const fetchModels = vi.fn();

vi.mock('@/services/settingsClient', () => ({
  fetchModels: (...a: unknown[]) => fetchModels(...a),
}));

vi.mock('@/components/settings/AdvancedModelField', () => ({
  describeDataPolicy: (p: string | null) =>
    p === 'logged_and_trained_on' ? 'logged and trained on' : 'terms unknown',
}));

import { AnsweredBy } from './AnsweredBy';
import type { ChatAttribution } from '@/stores/chatStore';

const LOCAL: ChatAttribution = {
  model: 'qwen2.5:7b',
  provider: 'ollama',
  locality: 'local',
  chosenBy: 'zaram',
};

const MODELS = [
  { id: 'ollama:qwen2.5:7b', displayName: 'qwen2.5:7b', provider: 'ollama', locality: 'local', dataPolicy: null, selectableByDefault: true, fitsResident: true, residentBudgetBytes: null, sizeBytes: null, category: 'llm' },
  { id: 'ollama:bge-m3', displayName: 'bge-m3', provider: 'ollama', locality: 'local', dataPolicy: null, selectableByDefault: true, fitsResident: true, residentBudgetBytes: null, sizeBytes: null, category: 'embedding' },
  { id: 'openrouter:big', displayName: 'big-cloud-model', provider: 'openrouter', locality: 'cloud', dataPolicy: 'logged_and_trained_on', selectableByDefault: false, fitsResident: null, residentBudgetBytes: null, sizeBytes: null, category: 'llm' },
];

beforeEach(() => {
  fetchModels.mockResolvedValue(MODELS);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('the reply still says who answered', () => {
  it('names the model with no offer when none is wired', () => {
    render(<AnsweredBy attribution={LOCAL} />);

    expect(screen.getByTestId('answered-by').textContent).toContain('qwen2.5:7b');
    expect(screen.queryByTestId('ask-another')).toBeNull();
  });

  it('renders nothing at all without a model, offer or not', () => {
    const { container } = render(
      <AnsweredBy attribution={{ ...LOCAL, model: '' }} onAskAnother={() => {}} />,
    );

    expect(container.textContent).toBe('');
  });
});

describe('asking another model', () => {
  it('does not touch the network until the offer is pressed', async () => {
    render(<AnsweredBy attribution={LOCAL} onAskAnother={() => {}} />);

    // The assertion that matters: rendering a reply is not discovery.
    expect(fetchModels).not.toHaveBeenCalled();

    await userEvent.click(screen.getByTestId('ask-another'));

    await waitFor(() => expect(fetchModels).toHaveBeenCalledTimes(1));
  });

  it('offers other chat models and never the one that just answered', async () => {
    render(<AnsweredBy attribution={LOCAL} onAskAnother={() => {}} />);

    await userEvent.click(screen.getByTestId('ask-another'));

    await waitFor(() => expect(screen.getByText('big-cloud-model')).toBeTruthy());
    expect(screen.queryByText('bge-m3')).toBeNull();
    // It answered this reply; it is not an alternative to itself.
    expect(screen.queryByRole('button', { name: 'qwen2.5:7b' })).toBeNull();
  });

  it('sends the display name, which is what the chat path speaks', async () => {
    const asked = vi.fn();
    render(<AnsweredBy attribution={LOCAL} onAskAnother={asked} />);

    await userEvent.click(screen.getByTestId('ask-another'));
    await waitFor(() => expect(screen.getByText('big-cloud-model')).toBeTruthy());
    await userEvent.click(screen.getByText('big-cloud-model'));

    expect(asked).toHaveBeenCalledWith('big-cloud-model');
  });

  it('carries the data policy onto the cloud option', async () => {
    render(<AnsweredBy attribution={LOCAL} onAskAnother={() => {}} />);

    await userEvent.click(screen.getByTestId('ask-another'));
    await waitFor(() => expect(screen.getByText('big-cloud-model')).toBeTruthy());

    const title = screen.getByText('big-cloud-model').getAttribute('title') ?? '';
    expect(title).toContain('Leaves this device');
    expect(title).toContain('logged and trained on');
  });

  it('says so when there is no other model rather than showing an empty row', async () => {
    fetchModels.mockResolvedValue([MODELS[0], MODELS[1]]);
    render(<AnsweredBy attribution={LOCAL} onAskAnother={() => {}} />);

    await userEvent.click(screen.getByTestId('ask-another'));

    await waitFor(() => expect(screen.getByText(/no other model is available/i)).toBeTruthy());
  });

  it('names a failed lookup instead of claiming there are none', async () => {
    fetchModels.mockRejectedValue(new Error('gate refused'));
    render(<AnsweredBy attribution={LOCAL} onAskAnother={() => {}} />);

    await userEvent.click(screen.getByTestId('ask-another'));

    // A provider that could not be reached is a different problem from having
    // no other model, and saying the wrong one sends the user to fix nothing.
    await waitFor(() =>
      expect(screen.getByText(/could not reach the model list/i)).toBeTruthy(),
    );
  });
});
