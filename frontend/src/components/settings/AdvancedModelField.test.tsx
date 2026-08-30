/**
 * What the Advanced model field must say, and what it must never say.
 *
 * The field lets a person type any string at all, which is exactly the case
 * `_unplaceable_model_refusal` was built for. Everything asserted here is a
 * sentence a friendlier version of this component would get wrong: a name it
 * has not looked for called imaginary, a `:free` model offered without its
 * terms, or a saved name reading as permission for the destination.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import AdvancedModelField, { describeDataPolicy, findTypedModel } from './AdvancedModelField';
import type { DiscoveredModel } from '@/services/settingsClient';

function model(over: Partial<DiscoveredModel> = {}): DiscoveredModel {
  return {
    id: 'ollama:qwen2.5:7b',
    displayName: 'qwen2.5:7b',
    provider: 'ollama',
    locality: 'local',
    dataPolicy: 'never_leaves_device',
    selectableByDefault: true,
    fitsResident: true,
    sizeBytes: 4_000_000_000,
    residentBudgetBytes: 9_100_000_000,
    category: 'llm',
    ...over,
  };
}

const FREE_CLOUD = model({
  id: 'openrouter:mistralai/mistral-7b-instruct:free',
  displayName: 'mistralai/mistral-7b-instruct:free',
  provider: 'openrouter',
  locality: 'cloud',
  dataPolicy: 'logged_and_trained_on',
  selectableByDefault: false,
});

afterEach(cleanup);

async function open() {
  // `<details>` renders its children either way in jsdom; clicking the
  // summary is what a person does, so the test does it too.
  await userEvent.click(screen.getByText('Advanced'));
}

describe('choosing a model by name', () => {
  it('hands the typed name to the caller', async () => {
    const onChoose = vi.fn();
    render(<AdvancedModelField models={[model()]} chosen={null} onChoose={onChoose} />);
    await open();

    await userEvent.type(screen.getByLabelText('Type a model name'), 'ollama:qwen2.5:7b');
    await userEvent.click(screen.getByRole('button', { name: 'Use this model' }));

    expect(onChoose).toHaveBeenCalledWith('ollama:qwen2.5:7b');
  });

  it('trims what was pasted', async () => {
    const onChoose = vi.fn();
    render(<AdvancedModelField models={[model()]} chosen={null} onChoose={onChoose} />);
    await open();

    await userEvent.type(screen.getByLabelText('Type a model name'), '  ollama:qwen2.5:7b  ');
    await userEvent.click(screen.getByRole('button', { name: 'Use this model' }));

    expect(onChoose).toHaveBeenCalledWith('ollama:qwen2.5:7b');
  });

  it('does nothing on an empty field', async () => {
    const onChoose = vi.fn();
    render(<AdvancedModelField models={[model()]} chosen={null} onChoose={onChoose} />);
    await open();

    await userEvent.click(screen.getByRole('button', { name: 'Use this model' }));

    expect(onChoose).not.toHaveBeenCalled();
  });
});

describe('the terms are shown while the user is choosing', () => {
  it('states what happens to a prompt sent to a free cloud model', async () => {
    render(<AdvancedModelField models={[FREE_CLOUD]} chosen={null} onChoose={vi.fn()} />);
    await open();

    await userEvent.type(
      screen.getByLabelText('Type a model name'),
      'mistralai/mistral-7b-instruct:free',
    );

    expect(screen.getByTestId('advanced-model-policy').textContent).toContain(
      'may train on them',
    );
  });

  it('offers a model Zaram would not route to on its own', async () => {
    /** `selectableByDefault` is a routing gate, not a paternalism gate. The
     *  free model above carries `false` and is still selectable here. */
    const onChoose = vi.fn();
    render(<AdvancedModelField models={[FREE_CLOUD]} chosen={null} onChoose={onChoose} />);
    await open();

    await userEvent.type(
      screen.getByLabelText('Type a model name'),
      'mistralai/mistral-7b-instruct:free',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Use this model' }));

    expect(onChoose).toHaveBeenCalledWith('mistralai/mistral-7b-instruct:free');
  });

  it('never calls an unknown policy safe', () => {
    const sentence = describeDataPolicy(null);

    expect(sentence).toContain('unknown');
    for (const reassurance of ['nothing is sent', 'private', 'safe', 'no training']) {
      expect(sentence.toLowerCase()).not.toContain(reassurance);
    }
  });
});

describe('a name Zaram cannot place', () => {
  it('says so, and says what will happen', async () => {
    render(<AdvancedModelField models={[model()]} chosen={null} onChoose={vi.fn()} />);
    await open();

    await userEvent.type(
      screen.getByLabelText('Type a model name'),
      'anthropic/claude-sonnet-4.5',
    );

    expect(screen.getByTestId('advanced-model-unplaceable').textContent).toContain(
      'refuse to send',
    );
  });

  it('is not claimed before discovery has run', async () => {
    /** The backend refusal resolves every uncertainty to *no refusal*, because
     *  a guard built on our own missing bookkeeping fires hardest on the first
     *  message after a boot. This is the same rule on screen: `null` models is
     *  "not looked", never "not there". */
    render(<AdvancedModelField models={null} chosen={null} onChoose={vi.fn()} />);
    await open();

    await userEvent.type(
      screen.getByLabelText('Type a model name'),
      'anthropic/claude-sonnet-4.5',
    );

    expect(screen.queryByTestId('advanced-model-unplaceable')).toBeNull();
    expect(screen.getByTestId('advanced-model-unlooked').textContent).toContain(
      'has not looked for models yet',
    );
  });

  it('is not claimed off an empty catalogue either', async () => {
    render(<AdvancedModelField models={[]} chosen={null} onChoose={vi.fn()} />);
    await open();

    await userEvent.type(screen.getByLabelText('Type a model name'), 'something');

    expect(screen.queryByTestId('advanced-model-unplaceable')).toBeNull();
  });

  it('can still be chosen', async () => {
    /** A name may be typed for a provider the user is about to connect.
     *  Blocking the save would make the field useless for the case it exists
     *  for, and the refusal at send time is the real guard. */
    const onChoose = vi.fn();
    render(<AdvancedModelField models={[model()]} chosen={null} onChoose={onChoose} />);
    await open();

    await userEvent.type(screen.getByLabelText('Type a model name'), 'openai/gpt-4o');
    await userEvent.click(screen.getByRole('button', { name: 'Use this model' }));

    expect(onChoose).toHaveBeenCalledWith('openai/gpt-4o');
  });
});

describe('a typed name widens nothing', () => {
  it('says that naming a model permits nothing', async () => {
    render(<AdvancedModelField models={[FREE_CLOUD]} chosen={null} onChoose={vi.fn()} />);
    await open();

    expect(screen.getByText(/permits nothing/i)).toBeTruthy();
  });
});

describe('matching', () => {
  it('accepts either spelling the chat path accepts', () => {
    const models = [model()];

    expect(findTypedModel(models, 'ollama:qwen2.5:7b')?.id).toBe('ollama:qwen2.5:7b');
    expect(findTypedModel(models, 'qwen2.5:7b')?.id).toBe('ollama:qwen2.5:7b');
  });

  it('does not fold case, because a model id does not', () => {
    expect(findTypedModel([model()], 'QWEN2.5:7B')).toBeNull();
  });

  it('has nothing to match against before discovery', () => {
    expect(findTypedModel(null, 'qwen2.5:7b')).toBeNull();
  });
});
