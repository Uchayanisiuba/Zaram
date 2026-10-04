/**
 * The context control offers a decision, not a number to re-pick.
 *
 * Asked for 4 October 2026: *"I don't want users to need to switch token
 * limits every time they switch or download a new model, there needs to
 * be a more elegant alternative."* The flaw being fixed is that one
 * stored figure cannot be right for two models, so what the control
 * stores is an intent and the figure is resolved per model.
 *
 * These assert the parts a backend test cannot reach: that the ladder is
 * not drawn under a policy that ignores it, that opening the panel is
 * what triggers the lookup rather than rendering Settings, and that the
 * resolved figure arrives with its origin attached.
 */
import type { ComponentProps } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const fetchContextWindow = vi.fn();

vi.mock('@/services/contextWindowClient', async () => {
  const actual = await vi.importActual<
    typeof import('@/services/contextWindowClient')
  >('@/services/contextWindowClient');
  return { ...actual, fetchContextWindow: (model: string) => fetchContextWindow(model) };
});

import ContextWindowField from './ContextWindowField';

/** `qwen3-14b-16k` as the maintainer's machine really answers. */
function resolved(over: Record<string, unknown> = {}) {
  return {
    model: 'qwen3-14b-16k:latest',
    ceiling: 40_960,
    loaded: 16_384,
    resolved: 16_384,
    reason: '16k tokens, the most this card affords beside the weights',
    costPerToken: 163_840,
    settable: true,
    servedBy: 'ollama',
    ...over,
  };
}

type Props = ComponentProps<typeof ContextWindowField>;

function field(props: Partial<Props> = {}) {
  return (
    <ContextWindowField
      policy="fit"
      overrides={{}}
      model="qwen3-14b-16k:latest"
      onChoosePolicy={vi.fn()}
      onChooseForModel={vi.fn()}
      {...props}
    />
  );
}

beforeEach(() => {
  fetchContextWindow.mockReset().mockResolvedValue(resolved());
});

async function open() {
  await userEvent.click(screen.getByText('Advanced'));
}

describe('the decision', () => {
  it('offers two choices, and only two', async () => {
    /** **There were three for a day.** `fixed` honoured one typed number
     *  for every model, which is the chore `fit` exists to end, and it
     *  was the only branch that skipped the declared-ceiling cap. A mode
     *  with no use `fit` does not cover, and a bug history, is not worth
     *  keeping for symmetry. */
    render(field());
    await open();
    expect(screen.getByTestId('context-policy-fit')).toHaveTextContent('As much as fits');
    expect(screen.getByTestId('context-policy-server')).toBeTruthy();
    expect(screen.queryByTestId('context-policy-fixed')).toBeNull();
    expect(screen.queryByTestId('context-fixed')).toBeNull();
  });

  it('frames the second one as an off switch, not a limit', async () => {
    // "Leave it to the server" is a different kind of thing from a
    // window somebody chose, and the label has to carry that or it
    // reads as the small option.
    render(field());
    await open();
    expect(screen.getByTestId('context-policy-server')).toHaveTextContent(
      'Leave it to the server',
    );
  });

  it('marks the policy in force', async () => {
    render(field({ policy: 'server' }));
    await open();
    expect(screen.getByTestId('context-policy-server')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('context-policy-fit')).toHaveAttribute('aria-pressed', 'false');
  });

  it('says what each choice costs, not only what it is called', async () => {
    // The part nobody can see, so it is the part that has to be written
    // down. "As much as fits" without "nothing to set" is a name.
    render(field());
    await open();
    expect(screen.getByTestId('context-policy-fit')).toHaveTextContent('Nothing to set');
  });

  it('reports the choice when one is made', async () => {
    const onChoosePolicy = vi.fn();
    render(field({ onChoosePolicy }));
    await open();
    await userEvent.click(screen.getByTestId('context-policy-server'));
    expect(onChoosePolicy).toHaveBeenCalledWith('server');
  });
});

describe('the resolved window', () => {
  it('is not looked up until the panel is opened', () => {
    // Rule 7g's posture at the smallest scale: reading Settings must not
    // make a network call as a side effect of being looked at.
    render(field());
    expect(fetchContextWindow).not.toHaveBeenCalled();
  });

  it('is looked up for the selected model once it is', async () => {
    render(field());
    await open();
    await waitFor(() => expect(fetchContextWindow).toHaveBeenCalledWith('qwen3-14b-16k:latest'));
  });

  it('names where the figure came from', async () => {
    /** The whole point of `reason`. 16k *from the card* and 16k *because
     *  you set it* are the same number and different facts. */
    render(field());
    await open();
    await waitFor(() =>
      expect(screen.getByTestId('context-resolved')).toHaveTextContent(
        'the most this card affords',
      ),
    );
  });

  it('prices the cache in memory, because that is what a window costs', async () => {
    render(field());
    await open();
    // 16,384 x 163,840 bytes = 2.7 GB.
    await waitFor(() =>
      expect(screen.getByTestId('context-resolved')).toHaveTextContent('2.7 GB'),
    );
  });

  it('prices nothing when the cache cannot be priced', async () => {
    /** `gemma4:12b` is this case and it is not an edge one: its
     *  sliding-window layers make the cost unreadable, and rendering
     *  `0 GB` would say context is free. */
    fetchContextWindow.mockResolvedValue(
      resolved({
        model: 'gemma4:12b',
        resolved: 131_072,
        costPerToken: null,
        reason: "128k tokens, what the model's own file asks for",
        loaded: 131_072,
      }),
    );
    render(field({ model: 'gemma4:12b' }));
    await open();
    await waitFor(() => expect(screen.getByTestId('context-resolved')).toBeTruthy());
    expect(screen.getByTestId('context-resolved')).not.toHaveTextContent('GB');
    expect(screen.getByTestId('context-resolved')).toHaveTextContent("own file");
  });

  it('says so when the loaded window is not the resolved one', async () => {
    /** The measured gap this whole module exists for: a model declaring
     *  262,144 that loaded with 4,096. Silence there reads as the setting
     *  not having worked. */
    fetchContextWindow.mockResolvedValue(resolved({ loaded: 4_096, resolved: 16_384 }));
    render(field());
    await open();
    await waitFor(() =>
      expect(screen.getByTestId('context-resolved')).toHaveTextContent('loaded with 4k tokens'),
    );
  });

  it('renders without the explanation when the lookup fails', async () => {
    // Never throws, and a control that failed to draw because Ollama was
    // slow is worse than one that draws without the note.
    fetchContextWindow.mockResolvedValue(null);
    render(field());
    await open();
    expect(screen.getByTestId('context-policy-fit')).toBeTruthy();
    expect(screen.queryByTestId('context-resolved')).toBeNull();
  });
});

describe('a window Zaram does not own', () => {
  /** The model that answers on the maintainer's machine is served by
   *  TabbyAPI, which fixes its window when it loads. `num_ctx` is an
   *  Ollama request field and has no equivalent there, so the figure is
   *  reported and the controls over it would settle nothing. */
  const tabby = {
    model: 'Qwen3.8-27B-exl3-2.20bpw',
    ceiling: 65_536,
    loaded: 65_536,
    resolved: 65_536,
    reason: "64k tokens, what the model's own file asks for",
    costPerToken: null,
    settable: false,
    servedBy: 'local server',
  };

  it('still reports the window, which is the 32x fix', async () => {
    fetchContextWindow.mockResolvedValue(tabby);
    render(field({ model: '' }));
    await open();
    await waitFor(() =>
      expect(screen.getByTestId('context-resolved')).toHaveTextContent('64k tokens'),
    );
  });

  it('says whose window it is', async () => {
    fetchContextWindow.mockResolvedValue(tabby);
    render(field({ model: '' }));
    await open();
    await waitFor(() =>
      expect(screen.getByTestId('context-resolved')).toHaveTextContent(
        'belongs to the server holding this model',
      ),
    );
  });

  it('offers no control over it', async () => {
    fetchContextWindow.mockResolvedValue(tabby);
    render(field({ model: '' }));
    await open();
    await waitFor(() => expect(screen.getByTestId('context-resolved')).toBeTruthy());
    expect(screen.queryByTestId('context-for-model')).toBeNull();
    expect(screen.queryByTestId('context-fixed')).toBeNull();
  });
});

describe('just for one model', () => {
  it('is what makes the default safe to disagree with', async () => {
    const onChooseForModel = vi.fn();
    render(field({ onChooseForModel }));
    await open();
    await waitFor(() => expect(fetchContextWindow).toHaveBeenCalled());
    await userEvent.click(screen.getByTestId('context-model-32768'));
    expect(onChooseForModel).toHaveBeenCalledWith('qwen3-14b-16k:latest', 32_768);
  });

  it('offers nothing past what the model declares it can hold', async () => {
    /** A control that accepts a number and shows a smaller one back is
     *  the shape of a product that looks broken, and the backend does cap
     *  it — so the offer must not be made. */
    render(field());
    await open();
    await waitFor(() => expect(screen.getByTestId('context-for-model')).toBeTruthy());
    // Ceiling 40,960: 32k is offered, 64k and 128k are not.
    expect(screen.getByTestId('context-model-32768')).toBeTruthy();
    expect(screen.queryByTestId('context-model-65536')).toBeNull();
    expect(screen.queryByTestId('context-model-131072')).toBeNull();
  });

  it('marks a window already set for this model', async () => {
    render(field({ overrides: { 'qwen3-14b-16k:latest': 8_192 } }));
    await open();
    expect(screen.getByTestId('context-model-8192')).toHaveAttribute('aria-pressed', 'true');
  });

  it('clears the entry rather than storing a zero', async () => {
    /** *"No opinion about this model"* and *"this model uses the server
     *  default"* are different states, and the first is the one this
     *  button means. */
    const onChooseForModel = vi.fn();
    render(field({ overrides: { 'qwen3-14b-16k:latest': 8_192 }, onChooseForModel }));
    await open();
    await userEvent.click(screen.getByTestId('context-model-0'));
    expect(onChooseForModel).toHaveBeenCalledWith('qwen3-14b-16k:latest', 0);
  });

  it('is about the model that would answer when nobody chose one', async () => {
    /** **This test asserted the opposite until the panel was looked at on
     *  screen.** It claimed the row was not drawn with no model selected,
     *  which was true and was the defect: an explicit default is the
     *  third of the three tiers of control, so on the common setup the
     *  useful half of the panel rendered nothing at all.
     *
     *  The backend resolves which model would answer and names it in the
     *  reply. The interface must not guess at it, because "never render
     *  invented values" applies hardest to a figure about memory. */
    fetchContextWindow.mockResolvedValue(resolved({ model: 'picked-for-you:8b' }));
    render(field({ model: '' }));
    await open();
    await waitFor(() => expect(fetchContextWindow).toHaveBeenCalledWith(''));
    expect(screen.getByTestId('context-for-model')).toHaveTextContent('picked-for-you:8b');
  });

  it('writes an override against the model that came back', async () => {
    // Not against the empty prop: that would store a window set for no
    // model at all, invisible and permanent.
    const onChooseForModel = vi.fn();
    fetchContextWindow.mockResolvedValue(resolved({ model: 'picked-for-you:8b' }));
    render(field({ model: '', onChooseForModel }));
    await open();
    await waitFor(() => expect(screen.getByTestId('context-for-model')).toBeTruthy());
    await userEvent.click(screen.getByTestId('context-model-8192'));
    expect(onChooseForModel).toHaveBeenCalledWith('picked-for-you:8b', 8_192);
  });
});
