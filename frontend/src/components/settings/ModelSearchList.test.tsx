/**
 * @vitest-environment jsdom
 *
 * Typing to find a model, and the free mark that must never stand alone.
 *
 * Asked for on 3 October 2026: *"OpenRouter comes with a lot of models and
 * it's currently a drag to navigate"*, with free tiers highlighted the way
 * other tools do it.
 *
 * The badge is the half with a rule attached. `CLAUDE.md` says naming the
 * deal is a primary feature of the picker and that a label saying "free"
 * alone is **the offer without the deal** — so the test that matters here is
 * not that the badge renders, it is that the badge never renders without the
 * sentence saying what the free tier costs instead. A green chip on its own
 * is the thing this product exists not to ship, and it is one careless commit
 * away at any time.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';

import ModelSearchList, {
  SEARCH_APPEARS_ABOVE,
  groupForSearch,
  matchesQuery,
  shortDataPolicy,
} from './ModelSearchList';
import type { DiscoveredModel } from '@/services/settingsClient';

function model(over: Partial<DiscoveredModel> & { id: string }): DiscoveredModel {
  return {
    displayName: over.id,
    provider: 'ollama',
    locality: 'local',
    dataPolicy: null,
    selectableByDefault: true,
    supportsTools: true,
    fitsResident: true,
    sizeBytes: null,
    residentCostBytes: null,
    residentBudgetBytes: null,
    category: 'llm',
    supportsVision: false,
    supportsEmbedding: false,
    specialisation: '',
    isFree: null,
    ...over,
  };
}

/** Enough rows that the search box renders, named so a query can narrow. */
function many(): DiscoveredModel[] {
  return [
    model({ id: 'nvidia/nemotron-3-nano', locality: 'cloud', provider: 'openrouter', isFree: true, dataPolicy: 'logged_and_trained_on' }),
    model({ id: 'nvidia/nemotron-3-super', locality: 'cloud', provider: 'openrouter', isFree: false, dataPolicy: 'not_trained_on' }),
    model({ id: 'moonshot/kimi-k2', locality: 'cloud', provider: 'openrouter', isFree: false, dataPolicy: 'not_trained_on' }),
    model({ id: 'openai/gpt-astra', locality: 'cloud', provider: 'openrouter', isFree: null }),
    model({ id: 'gemma4:12b' }),
    model({ id: 'qwen3-14b-16k' }),
    model({ id: 'llama3:8b' }),
    model({ id: 'mistral:7b' }),
    model({ id: 'phi4:14b' }),
  ];
}

describe('matchesQuery', () => {
  it('matches nothing typed', () => {
    expect(matchesQuery(model({ id: 'anything' }), '')).toBe(true);
    expect(matchesQuery(model({ id: 'anything' }), '   ')).toBe(true);
  });

  it('matches the name a person can see', () => {
    expect(matchesQuery(model({ id: 'x', displayName: 'Nemotron 3 Nano' }), 'nemo')).toBe(true);
  });

  it('matches the id somebody would paste', () => {
    const m = model({ id: 'nvidia/nemotron-3-nano', displayName: 'Nemotron 3 Nano' });
    expect(matchesQuery(m, 'nvidia/nemo')).toBe(true);
  });

  it('matches the provider', () => {
    expect(matchesQuery(model({ id: 'x', provider: 'openrouter' }), 'openrouter')).toBe(true);
  });

  it('ignores case', () => {
    expect(matchesQuery(model({ id: 'Kimi-K2' }), 'kimi')).toBe(true);
  });

  it('narrows on every term rather than widening', () => {
    const nano = model({ id: 'nvidia/nemotron-nano', isFree: true });
    const supr = model({ id: 'nvidia/nemotron-super', isFree: false });
    expect(matchesQuery(nano, 'nemotron nano')).toBe(true);
    expect(matchesQuery(supr, 'nemotron nano')).toBe(false);
  });

  it('finds a free model by the word a person would type', () => {
    // Without this the badge is findable by eye and not by keyboard, which
    // on a list of several hundred is most of the feature missing.
    expect(matchesQuery(model({ id: 'a', isFree: true }), 'free')).toBe(true);
    expect(matchesQuery(model({ id: 'b', isFree: false }), 'free')).toBe(false);
    expect(matchesQuery(model({ id: 'c', isFree: null }), 'free')).toBe(false);
  });
});

describe('groupForSearch', () => {
  it('splits by locality and shows the policy on cloud only', () => {
    const groups = groupForSearch([
      model({ id: 'local-one' }),
      model({ id: 'cloud-one', locality: 'cloud' }),
    ]);
    expect(groups.map((g) => g.key)).toEqual(['local', 'cloud']);
    expect(groups.find((g) => g.key === 'local')!.policy).toBe(false);
    expect(groups.find((g) => g.key === 'cloud')!.policy).toBe(true);
  });

  it('names a locality it does not recognise rather than hiding the model', () => {
    const groups = groupForSearch([model({ id: 'odd', locality: 'hybrid' })]);
    expect(groups).toHaveLength(1);
    expect(groups[0].key).toBe('other');
    // Unknown is the answer, so the terms are shown.
    expect(groups[0].policy).toBe(true);
  });

  it('leaves out a group with nothing in it', () => {
    expect(groupForSearch([model({ id: 'only-local' })]).map((g) => g.key)).toEqual(['local']);
  });
});

describe('the free badge', () => {
  it('marks a free model', () => {
    render(<ModelSearchList models={many()} value="" matchOn="id" onChoose={vi.fn()} decideLabel="Zaram decides" />);
    expect(screen.getAllByTestId('free-badge')).toHaveLength(1);
  });

  it('does not mark a priced model, nor one whose price is unknown', () => {
    // Three-valued on purpose: an unknown price is not a free one, and
    // guessing would put a green chip on something that charges.
    render(
      <ModelSearchList
        models={[
          model({ id: 'priced', locality: 'cloud', isFree: false }),
          model({ id: 'unknown', locality: 'cloud', isFree: null }),
        ]}
        value=""
        matchOn="id"
        onChoose={vi.fn()}
        decideLabel="Zaram decides"
      />,
    );
    expect(screen.queryByTestId('free-badge')).toBeNull();
  });

  it('never stands alone — the deal is named in the same row', () => {
    // The rule, asserted directly. `CLAUDE.md`: a label that says "free"
    // alone is the offer without the deal.
    render(
      <ModelSearchList
        models={[
          model({
            id: 'nvidia/free-one',
            locality: 'cloud',
            isFree: true,
            dataPolicy: 'logged_and_trained_on',
          }),
        ]}
        value=""
        matchOn="id"
        onChoose={vi.fn()}
        decideLabel="Zaram decides"
      />,
    );
    const badge = screen.getByTestId('free-badge');
    const row = badge.closest('button');
    expect(row).not.toBeNull();
    // Whatever the wording, the row has to say more than the badge does.
    const said = within(row as HTMLElement).getByText(/train|logged|kept|not used/i);
    expect(said).toBeTruthy();
  });
});

describe('searching', () => {
  it('does not put a search field over a short list', () => {
    render(
      <ModelSearchList
        models={[model({ id: 'a' }), model({ id: 'b' })]}
        value=""
        matchOn="id"
        onChoose={vi.fn()}
        decideLabel="Zaram decides"
      />,
    );
    expect(screen.queryByTestId('model-search-input')).toBeNull();
  });

  it('offers one once there are enough to be a drag', () => {
    const models = many();
    expect(models.length).toBeGreaterThan(SEARCH_APPEARS_ABOVE);
    render(<ModelSearchList models={models} value="" matchOn="id" onChoose={vi.fn()} decideLabel="Zaram decides" />);
    expect(screen.getByTestId('model-search-input')).toBeTruthy();
  });

  it('narrows the list as you type, across both groups', () => {
    render(<ModelSearchList models={many()} value="" matchOn="id" onChoose={vi.fn()} decideLabel="Zaram decides" />);
    expect(screen.getByText('gemma4:12b')).toBeTruthy();

    fireEvent.change(screen.getByTestId('model-search-input'), { target: { value: 'nemotron' } });

    expect(screen.queryByText('gemma4:12b')).toBeNull();
    expect(screen.getByText('nvidia/nemotron-3-nano')).toBeTruthy();
    expect(screen.getByText('nvidia/nemotron-3-super')).toBeTruthy();
  });

  it('finds the free ones by typing free', () => {
    render(<ModelSearchList models={many()} value="" matchOn="id" onChoose={vi.fn()} decideLabel="Zaram decides" />);
    fireEvent.change(screen.getByTestId('model-search-input'), { target: { value: 'free' } });
    expect(screen.getByText('nvidia/nemotron-3-nano')).toBeTruthy();
    expect(screen.queryByText('moonshot/kimi-k2')).toBeNull();
  });

  it('says nothing matched, which is not the same as having no models', () => {
    render(<ModelSearchList models={many()} value="" matchOn="id" onChoose={vi.fn()} decideLabel="Zaram decides" />);
    fireEvent.change(screen.getByTestId('model-search-input'), { target: { value: 'zzzz' } });
    expect(screen.getByTestId('model-search-none')).toBeTruthy();
  });

  it('keeps the way out visible while searching', () => {
    // A filtered list that hides "Zaram decides" strands somebody who typed
    // a typo with no way back to the default.
    render(<ModelSearchList models={many()} value="gemma4:12b" matchOn="id" onChoose={vi.fn()} decideLabel="Zaram decides" />);
    fireEvent.change(screen.getByTestId('model-search-input'), { target: { value: 'zzzz' } });
    expect(screen.getByText('Zaram decides')).toBeTruthy();
  });

  it('clears back to the whole list', () => {
    render(<ModelSearchList models={many()} value="" matchOn="id" onChoose={vi.fn()} decideLabel="Zaram decides" />);
    fireEvent.change(screen.getByTestId('model-search-input'), { target: { value: 'nemotron' } });
    expect(screen.queryByText('gemma4:12b')).toBeNull();

    fireEvent.click(screen.getByLabelText('Clear search'));
    expect(screen.getByText('gemma4:12b')).toBeTruthy();
  });
});

describe('choosing', () => {
  it('sends the field the surface stores', () => {
    // Settings stores the id, the composer stores the display name. Getting
    // this wrong writes a setting that resolves to nothing.
    const chose = vi.fn();
    render(
      <ModelSearchList
        models={[model({ id: 'nvidia/nemo', displayName: 'Nemotron' })]}
        value=""
        matchOn="displayName"
        onChoose={chose}
        decideLabel="Let Zaram decide"
      />,
    );
    fireEvent.click(screen.getByText('Nemotron'));
    expect(chose).toHaveBeenCalledWith('Nemotron');
  });

  it('hands the choice back when the chosen one is pressed again', () => {
    const chose = vi.fn();
    render(
      <ModelSearchList
        models={[model({ id: 'gemma4:12b' })]}
        value="gemma4:12b"
        matchOn="id"
        onChoose={chose}
        decideLabel="Zaram decides"
      />,
    );
    fireEvent.click(screen.getByText('gemma4:12b'));
    expect(chose).toHaveBeenCalledWith('');
  });

  it('offers a model Zaram would not auto-route to', () => {
    // `selectableByDefault` gates auto-routing, never the user asking.
    // Filtering those out here would hide a model somebody installed.
    render(
      <ModelSearchList
        models={[model({ id: 'free/one', locality: 'cloud', isFree: true, selectableByDefault: false })]}
        value=""
        matchOn="id"
        onChoose={vi.fn()}
        decideLabel="Zaram decides"
      />,
    );
    expect(screen.getByText('free/one')).toBeTruthy();
  });
});

describe('the deal, at list length', () => {
  it('says it in a few words rather than a sentence', () => {
    // `describeDataPolicy` writes a sentence, which is right where one model
    // is in question and a wall where five hundred are. Seen on screen with
    // the maintainer's own 549 models: every row repeating "Terms unknown.
    // Zaram will not route here on its own — choosing it is your decision,
    // and Activity records what went." The tests passed and it was unusable.
    expect(shortDataPolicy('logged_and_trained_on').length).toBeLessThan(40);
    expect(shortDataPolicy(null).length).toBeLessThan(40);
  });

  it('still names what a free tier costs', () => {
    // The short form is shorter, never softer. `CLAUDE.md`: naming the deal
    // is a primary feature of the picker.
    expect(shortDataPolicy('logged_and_trained_on')).toMatch(/train/i);
  });

  it('does not turn unknown into a reassuring blank', () => {
    // `DataPolicy` refuses to make unknown a member precisely because it
    // would start looking like a choice. Silence here would do the same.
    expect(shortDataPolicy(null)).toMatch(/unknown/i);
    expect(shortDataPolicy('something-nobody-has-heard-of')).toMatch(/unknown/i);
  });

  it('keeps the whole sentence within reach', () => {
    render(
      <ModelSearchList
        models={[model({ id: 'cloudy', locality: 'cloud', dataPolicy: 'logged_and_trained_on' })]}
        value=""
        matchOn="id"
        onChoose={vi.fn()}
        decideLabel="Zaram decides"
      />,
    );
    const short = screen.getByText(shortDataPolicy('logged_and_trained_on'));
    // Shortened on the row, whole on hover — nothing is dropped.
    expect(short.getAttribute('title')).toMatch(/logs prompts/i);
  });
});
